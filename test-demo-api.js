#!/usr/bin/env node
/**
 * Quick test script for demo API routes
 * Run: node test-demo-api.js
 */

const BASE = 'http://localhost:3002';

async function test(name, url, options = {}) {
  try {
    const res = await fetch(url, options);
    const data = await res.json();
    console.log(`✅ ${name}: ${res.status}`);
    return data;
  } catch (err) {
    console.log(`❌ ${name}: ${err.message}`);
    return null;
  }
}

async function main() {
  console.log('Testing PARWA Demo Pack APIs...\n');

  // Test 1: List Variants
  const variants = await test('List Variants', `${BASE}/api/demo/variants`);
  if (variants) {
    console.log(`   → ${variants.variants?.length || 0} variants, ${variants.industries?.length || 0} industries`);
  }

  // Test 2: Create Session
  const session = await test('Create Session', `${BASE}/api/demo/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      variant_id: 'growth',
      variant_tier: 'growth',
      industry: 'ecommerce',
      entry_source: 'demo_pack',
    }),
  });
  if (session?.session) {
    console.log(`   → Session: ${session.session.id}, Status: ${session.session.status}`);
    console.log(`   → Messages: ${session.session.messages_limit}, Call: ${session.session.call_seconds_limit}s`);

    // Test 3: Get Usage
    const usage = await test('Get Usage', `${BASE}/api/demo/usage?session_id=${session.session.id}`);
    if (usage?.usage) {
      console.log(`   → Messages: ${usage.usage.user_messages_sent}/${usage.usage.user_messages_limit}`);
    }

    // Test 4: Get Billing
    const billing = await test('Get Billing', `${BASE}/api/demo/billing?session_id=${session.session.id}`);
    if (billing?.bill_summary) {
      console.log(`   → Total: $${billing.bill_summary.total}, Savings: ${billing.bill_summary.savings_percentage}%`);
    }
  }

  // Test 5: List Knowledge Bases
  const kbs = await test('List KBs', `${BASE}/api/demo/knowledge-base`);
  if (kbs) {
    console.log(`   → Prebuilt: ${kbs.prebuilt?.length || 0}, Uploaded: ${kbs.uploaded?.length || 0}`);
  }

  // Test 6: Billing Estimate
  const estimate = await test('Bill Estimate', `${BASE}/api/demo/billing`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      variant_id: 'growth',
      ticket_volume: 5000,
      industry: 'ecommerce',
    }),
  });
  if (estimate?.bill_summary) {
    console.log(`   → Total: $${estimate.bill_summary.total}, Savings: ${estimate.bill_summary.savings_percentage}%`);
  }

  console.log('\nDone!');
}

main();
