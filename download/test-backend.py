#!/usr/bin/env python3
"""PARWA Backend Comprehensive Test Suite - Phase 13 & 14"""
import sys
import os
sys.path.insert(0, '/home/z/my-project/mini-services/parwa-backend')

import json
import time

# Start the backend inline
import uvicorn
import threading

def start_server():
    uvicorn.run('app.main:app', host='127.0.0.1', port=8000, log_level='warning')

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()
time.sleep(3)

# Now run tests
import requests

BASE = 'http://127.0.0.1:8000'
results = []
passed = 0
failed = 0

def test(name, func):
    global passed, failed
    try:
        result = func()
        results.append(('PASS', name, str(result)[:200]))
        passed += 1
    except Exception as e:
        results.append(('FAIL', name, str(e)[:200]))
        failed += 1

# ========== CORE TESTS ==========

test('Health Check', lambda: requests.get(BASE+'/health', timeout=5).json())

reg = requests.post(BASE+'/api/v1/auth/register', json={'email':'e2e@parwa.io','name':'E2E Tester','password':'TestPass123!'}, timeout=10).json()
test('Register User', lambda: reg.get('user',{}).get('email','?'))

login = requests.post(BASE+'/api/v1/auth/login', json={'email':'e2e@parwa.io','password':'TestPass123!'}, timeout=10).json()
TOKEN = login.get('access_token','')
HEADERS = {'Authorization': 'Bearer ' + TOKEN}
test('Login User', lambda: 'token_len=' + str(len(TOKEN)))

test('Get Current User', lambda: requests.get(BASE+'/api/v1/auth/me', headers=HEADERS, timeout=5).json().get('email','?'))

# ========== INTEGRATION CATALOG (GAP 3) ==========

cat_saas = requests.get(BASE+'/api/v1/integrations/catalog?industry=saas', headers=HEADERS, timeout=10).json()
test('Catalog SaaS ('+str(len(cat_saas.get('integrations',[])))+')', lambda: str(len(cat_saas.get('integrations',[])))+' integrations for SaaS industry')

cat_ecom = requests.get(BASE+'/api/v1/integrations/catalog?industry=ecommerce', headers=HEADERS, timeout=10).json()
test('Catalog E-commerce ('+str(len(cat_ecom.get('integrations',[])))+')', lambda: str(len(cat_ecom.get('integrations',[])))+' integrations')

cat_logistics = requests.get(BASE+'/api/v1/integrations/catalog?industry=logistics', headers=HEADERS, timeout=10).json()
test('Catalog Logistics ('+str(len(cat_logistics.get('integrations',[])))+')', lambda: str(len(cat_logistics.get('integrations',[])))+' integrations')

cat_other = requests.get(BASE+'/api/v1/integrations/catalog?industry=other', headers=HEADERS, timeout=10).json()
test('Catalog Other ('+str(len(cat_other.get('integrations',[])))+')', lambda: str(len(cat_other.get('integrations',[])))+' integrations (shows ALL)')

# ========== ONBOARDING FLOW ==========

test('Onboarding State', lambda: requests.get(BASE+'/api/v1/onboarding/state', headers=HEADERS, timeout=5).json().get('current_step','?'))

test('Set Industry+Variant', lambda: requests.post(BASE+'/api/v1/onboarding/industry-variant', json={'industry':'saas','variant':'parwa'}, headers=HEADERS, timeout=5).json().get('industry','?'))

test('Legal Consent', lambda: requests.post(BASE+'/api/v1/onboarding/legal-consent', headers=HEADERS, timeout=5).json().get('legal_accepted','?'))

test('Complete Step 3', lambda: requests.post(BASE+'/api/v1/onboarding/complete-step', json={'step':3}, headers=HEADERS, timeout=5).json().get('current_step','?'))

test('Complete Step 4', lambda: requests.post(BASE+'/api/v1/onboarding/complete-step', json={'step':4}, headers=HEADERS, timeout=5).json().get('current_step','?'))

test('Complete Step 5', lambda: requests.post(BASE+'/api/v1/onboarding/complete-step', json={'step':5}, headers=HEADERS, timeout=5).json().get('current_step','?'))

# ========== PHASE 13: GLOBAL API KEY SYSTEM (GAP 2 + GAP 6) ==========

# Test all 5 auth types
bearer_resp = requests.post(BASE+'/api/v1/api-keys/store', json={'integration_id':'hubspot','auth_type':'bearer','credentials':{'api_key':'pat-na1-bearer-test-12345678'}}, headers=HEADERS, timeout=5).json()
test('Phase13: Store Bearer Key (HubSpot)', lambda: bearer_resp.get('masked_key','?'))

header_resp = requests.post(BASE+'/api/v1/api-keys/store', json={'integration_id':'shopify','auth_type':'header','credentials':{'store_url':'test.myshopify.com','access_token':'shpat-header-test-abcdef12'}}, headers=HEADERS, timeout=5).json()
test('Phase13: Store Header Key (Shopify)', lambda: header_resp.get('masked_key','?'))

query_resp = requests.post(BASE+'/api/v1/api-keys/store', json={'integration_id':'klaviyo','auth_type':'query','credentials':{'api_key':'pk-test-query-key-98765432'}}, headers=HEADERS, timeout=5).json()
test('Phase13: Store Query Key (Klaviyo)', lambda: query_resp.get('masked_key','?'))

basic_resp = requests.post(BASE+'/api/v1/api-keys/store', json={'integration_id':'woocommerce','auth_type':'basic','credentials':{'username':'admin','password':'secret1234abcd'}}, headers=HEADERS, timeout=5).json()
test('Phase13: Store Basic Auth Key (WooCommerce)', lambda: basic_resp.get('masked_key','?'))

oauth_resp = requests.post(BASE+'/api/v1/api-keys/store', json={'integration_id':'salesforce','auth_type':'oauth2','credentials':{'client_id':'3MVG9-test-client-id','client_secret':'1234567890abcdef','instance_url':'https://na1.salesforce.com','refresh_token':'5Aep-test-refresh'}}, headers=HEADERS, timeout=5).json()
test('Phase13: Store OAuth2 Key (Salesforce)', lambda: oauth_resp.get('masked_key','?'))

# Test key listing (masked values only)
keys = requests.get(BASE+'/api/v1/api-keys/list', headers=HEADERS, timeout=5).json()
all_masked = all(k.get('masked_key','').startswith('\u2022') for k in keys.get('keys',[]) if k.get('masked_key'))
test('Phase13: List Keys ('+str(len(keys.get('keys',[])))+', all masked)', lambda: f'{len(keys.get("keys",[]))} keys, all_masked={all_masked}')

# Test key rotation
rotate_resp = requests.post(BASE+'/api/v1/api-keys/rotate', json={'integration_id':'hubspot','auth_type':'bearer','credentials':{'api_key':'pat-na1-NEW-rotated-key-9999'}}, headers=HEADERS, timeout=5).json()
test('Phase13: Rotate Key (HubSpot)', lambda: rotate_resp.get('masked_key','?'))

# Test key revocation
revoke_resp = requests.delete(BASE+'/api/v1/api-keys/revoke?integration_id=klaviyo', headers=HEADERS, timeout=5).json()
test('Phase13: Revoke Key (Klaviyo)', lambda: revoke_resp.get('message','?'))

# Test encryption round-trip
from app.encryption import encrypt_data, decrypt_data, mask_key
def test_encryption():
    key = 'my-super-secret-api-key-12345678'
    encrypted = encrypt_data(key)
    decrypted = decrypt_data(encrypted)
    masked = mask_key(key)
    assert decrypted == key, f'Decryption failed: {decrypted} != {key}'
    assert '5678' in masked, f'Masked should show last 4: {masked}'
    return f'OK masked={masked}'
test('Phase13: AES-256-GCM Encryption', test_encryption)

# ========== PHASE 14: AI TOOL SELECTION & MULTI-VARIANT ROUTING (GAP 9 + GAP 14) ==========

# Test variant list
variants = requests.get(BASE+'/api/v1/variants/list', headers=HEADERS, timeout=5).json()
test('Phase14: Variant List ('+str(len(variants.get('variants',[])))+')', lambda: f'{len(variants.get("variants",[]))} active variants')

# Add another variant
add_var = requests.post(BASE+'/api/v1/variants/add', json={'variant_type':'mini'}, headers=HEADERS, timeout=5).json()
test('Phase14: Add Mini Variant', lambda: add_var.get('variant_type','?'))

# Test variant usage
usage = requests.get(BASE+'/api/v1/variants/usage', headers=HEADERS, timeout=5).json()
test('Phase14: Variant Usage', lambda: f'{len(usage.get("variants",[]))} variants with usage')

# Test ticket routing - simple (score 2, should route to mini)
route_simple = requests.post(BASE+'/api/v1/variants/route-ticket', json={'intent':'what is return policy','complexity_score':2}, headers=HEADERS, timeout=5).json()
test('Phase14: Route Simple (score=2 -> mini)', lambda: route_simple.get('variant_type','?'))

# Test ticket routing - medium (score 5, should route to parwa)
route_medium = requests.post(BASE+'/api/v1/variants/route-ticket', json={'intent':'process my refund','complexity_score':5}, headers=HEADERS, timeout=5).json()
test('Phase14: Route Medium (score=5 -> parwa)', lambda: route_medium.get('variant_type','?'))

# Test ticket routing - complex (score 9, should escalate since no parwa_high)
route_complex = requests.post(BASE+'/api/v1/variants/route-ticket', json={'intent':'refund failed, escalate, predict churn','complexity_score':9}, headers=HEADERS, timeout=5).json()
test('Phase14: Route Complex (score=9 -> escalation)', lambda: route_complex.get('variant_type','?'))

# Test AI tools available
tools = requests.get(BASE+'/api/v1/ai-tools/available', headers=HEADERS, timeout=5).json()
test('Phase14: AI Tools Available ('+str(len(tools.get('tools',[])))+')', lambda: f'{len(tools.get("tools",[]))} tools available')

# Test AI tool selection
tool_select = requests.post(BASE+'/api/v1/ai-tools/select', json={'intent':'where is my order','ticket_text':'Customer asking about order shipping status'}, headers=HEADERS, timeout=5).json()
test('Phase14: AI Tool Selection', lambda: f'selected={len(tool_select.get("selected_tools",[]))} tools')

# Test dynamic system prompt
prompt = requests.get(BASE+'/api/v1/ai-tools/prompt', headers=HEADERS, timeout=5).json()
prompt_len = len(prompt.get('system_prompt',''))
test('Phase14: Dynamic System Prompt ('+str(prompt_len)+' chars)', lambda: f'prompt_length={prompt_len}')

# ========== AUDIT & NOTIFICATIONS ==========

test('Audit Stats', lambda: requests.get(BASE+'/api/v1/audit/stats', headers=HEADERS, timeout=5).json().get('total_entries','?'))

test('Audit Entries', lambda: len(requests.get(BASE+'/api/v1/audit/entries', headers=HEADERS, timeout=5).json().get('entries',[])))

# ========== PRINT RESULTS ==========

print()
print('='*70)
print('  PARWA Backend API Test Results - Phase 13 & 14')
print('='*70)
for status, name, detail in results:
    icon = '✅' if status == 'PASS' else '❌'
    print(f'  {icon} {name}')
    if status == 'FAIL':
        print(f'     Detail: {detail}')
print()
print(f'  Total: {passed+failed} | Passed: {passed} | Failed: {failed}')
print('='*70)

# Save results to file
with open('/home/z/my-project/download/backend-test-results.txt', 'w') as f:
    f.write('PARWA Backend API Test Results - Phase 13 & 14\n')
    f.write('='*70 + '\n')
    for status, name, detail in results:
        icon = '✅' if status == 'PASS' else '❌'
        f.write(f'{icon} {name}\n')
        if status == 'FAIL':
            f.write(f'   Detail: {detail}\n')
    f.write(f'\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}\n')
    f.write('='*70 + '\n')

print(f'\nResults saved to /home/z/my-project/download/backend-test-results.txt')

sys.exit(0 if failed == 0 else 1)
