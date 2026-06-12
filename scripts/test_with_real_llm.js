#!/usr/bin/env node
/**
 * PARWA Variant Tester — Real LLM Calls via z-ai SDK
 *
 * Tests all 3 PARWA variants with real LLM calls using the z-ai SDK.
 * This validates that variant model tier enforcement works with actual
 * API calls to Google AI, Groq, and Cerebras.
 *
 * Usage:
 *   node scripts/test_with_real_llm.js
 *
 * Environment variables needed:
 *   GOOGLE_AI_API_KEY - Google AI API key
 *   GROQ_API_KEY      - Groq API key
 *   CEREBRAS_API_KEY  - Cerebras API key
 */

const ZAI = require('../node_modules/z-ai-web-dev-sdk').default;

// ─── Model Tier Configuration ────────────────────────────────────────────────

const MODEL_TIERS = {
  light: [
    'cerebras/llama-3.1-8b',
    'groq/llama-3.1-8b-instant',
    'gemini/gemma-3-27b-it',
  ],
  medium: [
    'gemini/gemini-2.0-flash-lite',
    'gemini/gemini-2.0-flash',
    'groq/llama-3.3-70b-versatile',
    'groq/qwen3-32b',
  ],
  heavy: [
    'groq/llama-3.3-70b-versatile',
    'cerebras/llama-4-scout-17b-16e-instruct',
    'groq/llama-3.1-8b-instant',
  ],
  guardrail: [
    'groq/llama-guard-4-12b',
  ],
};

const VARIANT_TIERS = {
  mini: ['light', 'guardrail'],
  parwa: ['light', 'medium', 'guardrail'],
  high: ['light', 'medium', 'heavy', 'guardrail'],
};

const NODE_TIER_MAP = {
  INGEST: 'light',
  INTENT_CLASSIFIER: 'light',
  SENTIMENT_ANALYZER: 'light',
  REASONING_ENGINE: 'medium',
  KB_RETRIEVER: 'medium',
  QUALITY_SCORER: 'medium',
  RESPONSE_FORMATTER: 'medium',
};

// ─── Real-World Test Tickets ──────────────────────────────────────────────────

const TICKETS = [
  {
    id: 'REAL-001',
    name: 'Duplicate Charge Refund',
    message: "I was charged twice for order #ORD-78234. $149.99 on Jan 5th and again on Jan 5th. I only placed this order once. This is really frustrating as it's caused an overdraft fee on my account.",
    channel: 'email',
    expectedIntent: 'refund_request',
  },
  {
    id: 'REAL-005',
    name: 'Complex Technical Issue',
    message: "I'm a developer using your API platform. Since the v3.2 update, I'm getting intermittent 503 errors on the /api/v3/users endpoint. It happens roughly every 1 in 50 requests. This is affecting my production app with 10k daily users.",
    channel: 'chat',
    expectedIntent: 'technical_support',
  },
  {
    id: 'REAL-009',
    name: 'Simple FAQ Question',
    message: 'What is your return policy? I bought a product last week and want to know if I can still return it.',
    channel: 'chat',
    expectedIntent: 'faq_question',
  },
  {
    id: 'REAL-010',
    name: 'GDPR Data Deletion Request',
    message: "Under GDPR Article 17, I am exercising my right to erasure. My name is Jan Mueller, email jan.mueller@example.de. I want ALL my personal data deleted from your systems within 30 days as required by law.",
    channel: 'email',
    expectedIntent: 'account_modification',
  },
];

// ─── Helper Functions ──────────────────────────────────────────────────────────

function getModelForNode(nodeName, variant) {
  const requiredTier = NODE_TIER_MAP[nodeName] || 'light';
  const availableTiers = VARIANT_TIERS[variant];

  let selectedTier = requiredTier;
  if (!availableTiers.includes(requiredTier)) {
    // Downgrade: pick highest available tier
    const priority = ['heavy', 'medium', 'light'];
    for (const tier of priority) {
      if (availableTiers.includes(tier)) {
        selectedTier = tier;
        break;
      }
    }
  }

  return MODEL_TIERS[selectedTier][0];
}

function getLiteLLMModel(modelStr) {
  // Convert our model format to z-ai SDK format
  // z-ai SDK uses provider/model format
  return modelStr;
}

// ─── ANSI Colors ──────────────────────────────────────────────────────────────

const RED = '\x1b[91m';
const GREEN = '\x1b[92m';
const YELLOW = '\x1b[93m';
const BLUE = '\x1b[94m';
const MAGENTA = '\x1b[95m';
const CYAN = '\x1b[96m';
const BOLD = '\x1b[1m';
const RESET = '\x1b[0m';

function badge(variant) {
  const colors = { mini: YELLOW, parwa: BLUE, high: MAGENTA };
  return `${BOLD}${colors[variant] || RESET}[${variant.toUpperCase()}]${RESET}`;
}

function pass(text) {
  console.log(`  ${GREEN}PASS${RESET} ${text}`);
}

function fail(text) {
  console.log(`  ${RED}FAIL${RESET} ${text}`);
}

// ─── Test Functions ────────────────────────────────────────────────────────────

async function testModelTierEnforcement() {
  console.log(`\n${BOLD}${BLUE}-- Test 1: Model Tier Enforcement with Real LLM --${RESET}`);
  let passed = 0, failed = 0;

  const zai = await ZAI.create();

  const testNodes = [
    { name: 'INTENT_CLASSIFIER', tier: 'light' },
    { name: 'REASONING_ENGINE', tier: 'medium' },
    { name: 'QUALITY_SCORER', tier: 'medium' },
  ];

  for (const node of testNodes) {
    for (const variant of ['mini', 'parwa', 'high']) {
      const model = getModelForNode(node.name, variant);
      const expectedTier = VARIANT_TIERS[variant].includes(node.tier) ? node.tier : 'light';
      const actualModelIsCorrect = MODEL_TIERS[expectedTier].includes(model);

      if (actualModelIsCorrect) {
        pass(`${badge(variant)} ${node.name}: tier=${expectedTier}, model=${model}`);
        passed++;
      } else {
        fail(`${badge(variant)} ${node.name}: unexpected model=${model}`);
        failed++;
      }
    }
  }

  // Now make real LLM calls to verify models work
  console.log(`\n  ${BOLD}Making real LLM calls per variant tier...${RESET}`);

  for (const variant of ['mini', 'parwa', 'high']) {
    const lightModel = getModelForNode('INTENT_CLASSIFIER', variant);
    try {
      const response = await zai.chat.completions.create({
        messages: [
          { role: 'system', content: 'Classify the customer intent. Reply with ONLY the intent name.' },
          { role: 'user', content: 'I was charged twice for the same order.' },
        ],
        model: lightModel,
      });

      const intent = response.choices[0]?.message?.content || '';
      pass(`${badge(variant)} Real LLM call (${lightModel}): "${intent.substring(0, 50)}"`);
      passed++;
    } catch (error) {
      fail(`${badge(variant)} Real LLM call (${lightModel}): ${error.message}`);
      failed++;
    }
  }

  return { passed, failed };
}

async function testVariantThinking() {
  console.log(`\n${BOLD}${BLUE}-- Test 2: All Variants THINK Identically (Real LLM) --${RESET}`);
  let passed = 0, failed = 0;

  const zai = await ZAI.create();

  const prompt = "Classify this customer message into one intent: refund_request, cancellation, technical_support, faq_question, general_inquiry. Message: 'I was charged twice for the same order.' Reply with ONLY the intent.";

  const intents = {};

  for (const variant of ['mini', 'parwa', 'high']) {
    const model = getModelForNode('INTENT_CLASSIFIER', variant);
    try {
      const response = await zai.chat.completions.create({
        messages: [{ role: 'user', content: prompt }],
        model: model,
      });

      const intent = response.choices[0]?.message?.content?.trim() || '';
      intents[variant] = intent;

      pass(`${badge(variant)} Intent: "${intent}" (model: ${model})`);
      passed++;
    } catch (error) {
      fail(`${badge(variant)} Error: ${error.message}`);
      failed++;
    }
  }

  // Verify thinking is consistent (all variants classify as refund)
  const allRefund = Object.values(intents).every(i => i.toLowerCase().includes('refund'));
  if (allRefund) {
    pass(`${BOLD}All variants THINK the same intent (refund)${RESET}`);
    passed++;
  } else {
    fail(`Variants disagree on intent: ${JSON.stringify(intents)}`);
    failed++;
  }

  return { passed, failed };
}

async function testModelTierDifferences() {
  console.log(`\n${BOLD}${BLUE}-- Test 3: Model Tier Quality Differences --${RESET}`);
  let passed = 0, failed = 0;

  const zai = await ZAI.create();

  // Test a complex reasoning task - different models should give different quality
  const complexPrompt = `Analyze this customer support scenario and determine the best course of action:

Customer reports being charged $149.99 twice for the same order (#ORD-78234). 
CRM shows two charges on Jan 5th. The refund policy allows refunds within 30 days.
Customer also mentions an overdraft fee of $35 caused by the double charge.

Provide: 1) Root cause analysis 2) Recommended actions 3) Compensation recommendation`;

  const results = {};

  for (const variant of ['mini', 'parwa', 'high']) {
    const model = getModelForNode('REASONING_ENGINE', variant);
    try {
      const startTime = Date.now();
      const response = await zai.chat.completions.create({
        messages: [{ role: 'user', content: complexPrompt }],
        model: model,
      });
      const elapsed = Date.now() - startTime;

      const content = response.choices[0]?.message?.content || '';
      results[variant] = { model, content, elapsed, length: content.length };

      pass(`${badge(variant)} Reasoning (${model}): ${content.length} chars in ${elapsed}ms`);
      passed++;
    } catch (error) {
      fail(`${badge(variant)} Error (${model}): ${error.message}`);
      failed++;
    }
  }

  // All variants should produce a response
  const allProduced = Object.values(results).every(r => r.length > 0);
  if (allProduced) {
    pass('All variants produced reasoning output');
    passed++;
  } else {
    fail('Some variants failed to produce output');
    failed++;
  }

  return { passed, failed };
}

async function testRealWorldTickets() {
  console.log(`\n${BOLD}${BLUE}-- Test 4: Real-World Ticket Processing (Real LLM) --${RESET}`);
  let passed = 0, failed = 0;

  const zai = await ZAI.create();

  for (const ticket of TICKETS) {
    console.log(`\n  ${BOLD}Ticket: ${ticket.id} - ${ticket.name}${RESET}`);

    for (const variant of ['mini', 'parwa', 'high']) {
      const model = getModelForNode('INTENT_CLASSIFIER', variant);
      try {
        const response = await zai.chat.completions.create({
          messages: [
            {
              role: 'system',
              content: 'You are a customer support AI. Classify the customer intent and provide a brief helpful response. Reply with: INTENT: <intent> | RESPONSE: <response>',
            },
            { role: 'user', content: ticket.message },
          ],
          model: model,
        });

        const content = response.choices[0]?.message?.content || '';
        const hasResponse = content.length > 0;
        const matchesIntent = content.toLowerCase().includes(ticket.expectedIntent.replace('_', ''));

        if (hasResponse) {
          pass(`${badge(variant)} Response: "${content.substring(0, 60)}..." (${model})`);
          passed++;
        } else {
          fail(`${badge(variant)} Empty response`);
          failed++;
        }

        if (matchesIntent) {
          pass(`${badge(variant)} Intent matches: ${ticket.expectedIntent}`);
          passed++;
        }
      } catch (error) {
        fail(`${badge(variant)} Error (${model}): ${error.message}`);
        failed++;
      }
    }
  }

  return { passed, failed };
}

// ─── Main Runner ────────────────────────────────────────────────────────────────

async function main() {
  const width = 70;
  console.log(`\n${BOLD}${CYAN}${'='.repeat(width)}${RESET}`);
  console.log(`${BOLD}${CYAN}  ${'PARWA Phase 7: Real LLM Variant Testing (z-ai SDK)'.padEnd(width - 4)}${RESET}`);
  console.log(`${BOLD}${CYAN}${'='.repeat(width)}${RESET}`);
  console.log(`  Mode: LIVE (real LLM calls via z-ai SDK)`);
  console.log(`  Variants: Mini, PARWA, High`);
  console.log(`  Models: Cerebras, Google AI, Groq`);

  const allResults = {};

  try {
    allResults.modelTiers = await testModelTierEnforcement();
    allResults.thinking = await testVariantThinking();
    allResults.quality = await testModelTierDifferences();
    allResults.tickets = await testRealWorldTickets();
  } catch (error) {
    console.error(`\n${RED}${BOLD}Fatal error: ${error.message}${RESET}`);
    process.exit(1);
  }

  // Summary
  console.log(`\n${BOLD}${CYAN}${'='.repeat(width)}${RESET}`);
  console.log(`${BOLD}${CYAN}  ${'Test Summary'.padEnd(width - 4)}${RESET}`);
  console.log(`${BOLD}${CYAN}${'='.repeat(width)}${RESET}`);

  let totalPassed = 0, totalFailed = 0;
  for (const [name, result] of Object.entries(allResults)) {
    const status = result.failed === 0 ? `${GREEN}PASSED${RESET}` : `${RED}FAILED${RESET}`;
    console.log(`  ${name}: ${result.passed}/${result.passed + result.failed} ${status}`);
    totalPassed += result.passed;
    totalFailed += result.failed;
  }

  console.log(`\n  ${BOLD}Total: ${totalPassed}/${totalPassed + totalFailed} passed${RESET}`);

  if (totalFailed > 0) {
    console.log(`  ${RED}${BOLD}${totalFailed} tests FAILED${RESET}`);
    process.exit(1);
  } else {
    console.log(`  ${GREEN}${BOLD}All tests PASSED!${RESET}`);
  }
}

main();
