#!/usr/bin/env python3
"""Synchronous honest resolution rate test using ZAI SDK."""
import subprocess, json, os, time, sys

TICKETS = [
    {"id": 1, "query": "I ordered a laptop 2 weeks ago and it still hasn't arrived!", "category": "shipping", "expected_intent": "shipping"},
    {"id": 2, "query": "I want a refund for the damaged headphones I received.", "category": "refund", "expected_intent": "refund"},
    {"id": 3, "query": "You charged me twice for the same order!", "category": "billing", "expected_intent": "billing"},
    {"id": 11, "query": "Our team can't access the dashboard. Getting 503 errors.", "category": "technical", "expected_intent": "technical"},
    {"id": 16, "query": "We want to cancel our subscription.", "category": "cancellation", "expected_intent": "cancellation"},
    {"id": 32, "query": "Unauthorized transaction of $3,450 on my account!", "category": "billing", "expected_intent": "billing"},
    {"id": 35, "query": "App crashed when depositing a check. Money gone.", "category": "technical", "expected_intent": "technical"},
    {"id": 38, "query": "I'm going to sue your company for selling my data.", "category": "legal_threat", "expected_intent": "escalation"},
    {"id": 40, "query": "What are your business hours?", "category": "general", "expected_intent": "general"},
    {"id": 25, "query": "Delivery driver left a $5,000 package outside. Now missing.", "category": "complaint", "expected_intent": "complaint"},
]

def zai_chat(system_prompt, user_message):
    of = f'/tmp/honest_{int(time.time()*1000)}.json'
    for attempt in range(3):
        try:
            r = subprocess.run(['z-ai', 'chat', '--prompt', user_message, '--system', system_prompt, '--output', of],
                              capture_output=True, text=True, timeout=60)
            if r.returncode == 0 and os.path.exists(of):
                with open(of) as f:
                    d = json.load(f)
                os.remove(of)
                content = d.get('choices',[{}])[0].get('message',{}).get('content','').strip()
                if content:
                    return content
            if "429" in r.stderr:
                print(f"    [Rate limited, retry {attempt+1}...]", flush=True)
                time.sleep(30 * (attempt + 1))
            else:
                print(f"    [z-ai error: {r.stderr[:80]}]", flush=True)
                time.sleep(10)
        except Exception as e:
            print(f"    [Exception: {e}]", flush=True)
            time.sleep(10)
    return ''

results = []
for i, t in enumerate(TICKETS):
    print(f"\n[{i+1}/{len(TICKETS)}] Ticket #{t['id']} ({t['category']})...", flush=True)
    start = time.time()
    
    # Step 1: Intent
    intent = zai_chat(
        'Classify into ONE word: refund, billing, technical, complaint, shipping, account, cancellation, general, escalation. Only the word.',
        f"Classify: {t['query']}"
    ).lower().strip()
    # Clean up intent
    for valid in ['refund','billing','technical','complaint','shipping','account','cancellation','general','escalation']:
        if valid in intent:
            intent = valid
            break
    else:
        intent = 'general'
    intent_correct = intent == t['expected_intent']
    print(f"  Intent: {intent} {'OK' if intent_correct else 'WRONG'} (expected: {t['expected_intent']})", flush=True)
    time.sleep(12)
    
    # Step 2: Response
    response = zai_chat(
        f"You are a customer service AI. Customer intent: {intent}. Be direct, 2-3 sentences. No filler phrases.",
        t['query']
    )
    print(f"  Response: {response[:80]}...", flush=True)
    time.sleep(12)
    
    # Step 3: Quality
    quality_str = zai_chat(
        'Rate this support response 0-100. Return ONLY a number.',
        f"Customer: {t['query']}\nResponse: {response}"
    )
    try:
        quality = float(''.join(c for c in quality_str if c.isdigit() or c=='.'))
    except:
        quality = 50.0
    print(f"  Quality: {quality:.0f}", flush=True)
    time.sleep(12)
    
    # Step 4: Resolution
    resolution = zai_chat(
        'Would this response solve the problem? Reply ONLY: fully_resolved, partially_resolved, or not_resolved',
        f"Customer: {t['query']}\nResponse: {response}"
    ).lower().strip()
    res_status = "not_resolved"
    if "fully_resolved" in resolution:
        res_status = "fully_resolved"
    elif "partially_resolved" in resolution:
        res_status = "partially_resolved"
    print(f"  Resolution: {res_status}", flush=True)
    
    latency = time.time() - start
    results.append({
        "id": t["id"], "category": t["category"], "expected": t["expected_intent"],
        "predicted": intent, "intent_correct": intent_correct,
        "quality": quality, "resolution": res_status,
        "response": response[:100], "latency_s": round(latency, 1)
    })
    
    if i < len(TICKETS) - 1:
        print(f"  Waiting 15s...", flush=True)
        time.sleep(15)

# Calculate metrics
total = len(results)
intent_acc = sum(1 for r in results if r['intent_correct']) / total * 100
fully_res = sum(1 for r in results if r['resolution'] == 'fully_resolved') / total * 100
partial_res = sum(1 for r in results if r['resolution'] == 'partially_resolved') / total * 100
true_res = sum(1 for r in results if r['intent_correct'] and r['resolution'] == 'fully_resolved') / total * 100
industry_res = sum(1 for r in results if r['resolution'] in ('fully_resolved','partially_resolved')) / total * 100
quality_pass = sum(1 for r in results if r['quality'] >= 60) / total * 100
contained = sum(1 for r in results if r['quality'] >= 40 and r['resolution'] != 'not_resolved') / total * 100

print(f"\n{'='*70}")
print(f"  HONEST RESOLUTION RATE (Real LLM - glm-4-plus via ZAI SDK)")
print(f"{'='*70}")
print(f"  Tickets: {total} | LLM calls: {total*4}")
print(f"  Containment: {contained:.1f}% | Intent: {intent_acc:.1f}%")
print(f"  Quality Pass: {quality_pass:.1f}% | Fully Resolved: {fully_res:.1f}%")
print(f"  Partially Resolved: {partial_res:.1f}%")
print(f"  TRUE RESOLUTION: {true_res:.1f}%")
print(f"  Industry-Comparable: {industry_res:.1f}%")

output = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "method": "real_llm_zai_sdk_glm4_plus",
    "total_tickets": total, "total_llm_calls": total*4,
    "metrics": {
        "intent_accuracy": round(intent_acc, 2),
        "quality_pass_rate": round(quality_pass, 2),
        "fully_resolved_rate": round(fully_res, 2),
        "partially_resolved_rate": round(partial_res, 2),
        "true_resolution_rate": round(true_res, 2),
        "industry_comparable_rate": round(industry_res, 2),
        "containment_rate": round(contained, 2),
    },
    "per_ticket": results
}
outpath = "/home/z/my-project/download/honest_resolution_rate_results.json"
os.makedirs(os.path.dirname(outpath), exist_ok=True)
with open(outpath, 'w') as f:
    json.dump(output, f, indent=2, default=str)
print(f"  Saved to: {outpath}")
print(f"{'='*70}")
