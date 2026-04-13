import sys
import os
import json
from typing import Any, Dict

# Set PYTHONPATH so we can import app
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# Mocking the database and models
class MockSession:
    def __init__(self):
        self.id = "test-session-123"
        self.type = "onboarding"
        self.context_json = json.dumps({
            "entry_source": "models_page",
            "industry": "E-commerce",
            "variant": "AI Agent 017",
            "pages_visited": ["pricing_page", "models_page"]
        })
        self.pack_type = "free"
        self.demo_call_used = False
        self.payment_status = "idle"

def test_intelligence():
    from app.services.jarvis_service import build_system_prompt
    from app.services.jarvis_knowledge_service import search_and_format_knowledge
    
    print("--- 🧪 Jarvis Intelligence Test 🧪 ---")
    
    # ── Test 1: System Prompt Context Awareness ──
    # Note: build_system_prompt normally queries DB, we'll mock the internal _parse_context and ctx retrieval if needed
    # But let's check the logic by looking at what it would output.
    
    # Simulate the context we built for the mock session
    ctx = {
        "entry_source": "models_page",
        "industry": "E-commerce",
        "variant": "AI Agent 017",
        "pages_visited": ["pricing_page", "models_page"],
        "detected_stage": "discovery"
    }
    
    print("\n[1] Testing Knowledge Retrieval...")
    search_q = "how much does it cost?"
    kb_results = search_and_format_knowledge(search_q, ctx)
    if "PRICING TIER" in kb_results:
        print("✅ Knowledge Retrieval: SUCCESS (Pricing found)")
    else:
        print("❌ Knowledge Retrieval: FAILED")
        print("KB Results:", kb_results)

    print("\n[2] Testing Prompt Construction...")
    # Since build_system_prompt uses a DB session, we'll just check if the service
    # correctly assembles the 'onboarding' persona when called.
    
    try:
        from app.services.jarvis_knowledge_service import build_context_knowledge
        ck = build_context_knowledge(ctx)
        if "Industry Context (E-commerce)" in ck:
            print("✅ Context Awareness: SUCCESS (Industry injected)")
        else:
            print("❌ Context Awareness: FAILED (Industry missing)")
            print("Context Knowledge:", ck)
    except Exception as e:
        print(f"❌ Context Awareness Error: {e}")

    print("\n[3] Testing Objection Handling...")
    ob_q = "it's too expensive"
    ob_kb = search_and_format_knowledge(ob_q, ctx)
    if "OBJECTION" in ob_kb:
        print("✅ Objection Handling: SUCCESS (Response found)")
    else:
        print("❌ Objection Handling: FAILED")

if __name__ == "__main__":
    test_intelligence()
