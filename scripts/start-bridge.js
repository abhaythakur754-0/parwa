#!/usr/bin/env node
/**
 * ZAI LLM Bridge — Persistent HTTP server wrapping z-ai-web-dev-sdk.
 *
 * Python PARWA pipeline sends POST /v1/chat with prompt + node_name,
 * this server calls zai SDK chat.completions.create() and returns the response.
 *
 * Usage: node scripts/start-bridge.js
 * Bridge runs on port 4789 (override with ZAI_BRIDGE_PORT env var)
 */

const http = require('http');
const ZAI = require('z-ai-web-dev-sdk').default;

const PORT = parseInt(process.env.ZAI_BRIDGE_PORT || '4789', 10);
const HOST = '127.0.0.1';

let zaiInstance = null;
let callCount = 0;
let errorCount = 0;

// System prompts per node — tells the AI what structured output format to use
const SYSTEM_PROMPTS = {
  INTENT_CLASSIFIER: 'Classify this customer message into ONE intent: order_status, refund_request, cancellation, billing_issue, technical_support, faq_question, complaint, account_modification, escalation, general_inquiry. Reply with ONLY: intent|confidence (e.g. refund_request|0.95)',
  SENTIMENT_ANALYZER: 'Analyze the sentiment of this customer message. Reply with ONLY: sentiment|urgency where sentiment is one of: happy, neutral, frustrated, angry and urgency is 0.0-1.0 (e.g. frustrated|0.8)',
  ESCALATION_DECISION: 'Should this ticket be escalated to a human agent? Reply with ONLY: true|reason or false| where reason is one of: legal_threat, high_urgency, complex_technical, vip_customer, angry_customer_with_critical_issue',
  FAQ_MATCHER: 'Does this message match any FAQ? Reply with ONLY: faq_id|relevance_score|content or no_match|0.00| where relevance is 0.0-1.0. Common FAQs: refund_policy, shipping_faq, return_policy, billing_faq, account_faq',
  KB_RETRIEVER: 'Retrieve relevant knowledge base information for this query. Provide a helpful, factual answer based on common customer support policies.',
  INTEGRATION_LOOKUP: 'Look up CRM data for this customer. Reply with a JSON object: {"order_id":"ORD-XXXX","status":"...","charges":[{"amount":0,"date":"..."}],"customer":{"name":"...","tier":"..."}}',
  REASONING_ENGINE: 'Think step-by-step about this customer issue. Provide a clear reasoning chain ending with: Conclusion: <your conclusion>',
  REVERSE_THINKER: 'Work backward from the desired outcome. Start with "Goal: <outcome>" then trace back through each requirement. End with "Validation: PASSED" or "Validation: FAILED".',
  TREE_OF_THOUGHTS: 'Explore 3 different solution paths for this problem. Format each as: Path N: <description> (confidence: 0.XX, selected: true/false). Select the best path.',
  STRATEGY_PLANNER: 'Create a step-by-step strategy plan to resolve this issue. Number each step and be specific about actions and evidence needed.',
  ACTION_PLANNER: 'Plan the specific actions needed to resolve this. Format: action_type: description (risk: low/medium/high). Valid action types: send_reply, process_refund, cancel_order, modify_account, escalate_to_human, share_faq, share_policy, create_note',
  PROACTIVE_CHECKER: 'What proactive follow-ups or predictions can we make for this customer? Suggest 1-2 insights with type (follow_up, prediction, cross_sell), description, and confidence.',
  PREDICTION_ENGINE: 'Predict what might happen next with this customer. Consider churn risk, upsell opportunities. Include confidence level.',
  QUALITY_SCORER: 'Score the quality of this customer service response on a scale of 0-100. Reply with ONLY: score|issues where issues are comma-separated (e.g. 85|accurate,complete,compliant or 45|incomplete,not_empathetic)',
  PII_COMPLIANCE_GUARD: 'Check this message for personally identifiable information (SSN, credit card numbers, email addresses, phone numbers, physical addresses). Reply with ONLY: true|details or false|No PII detected',
  RESPONSE_FORMATTER: 'Format a professional, empathetic customer service response based on the provided context. Be concise but thorough. Include specific details from the evidence.',
  FEEDBACK_LOOP: 'Analyze the customer satisfaction based on this interaction. Reply with: resolved: true/false, satisfaction: high/medium/low, improvement_areas: list',
};

async function initZAI() {
  if (!zaiInstance) {
    zaiInstance = await ZAI.create();
    process.stderr.write('[zai-bridge] ZAI SDK initialized\n');
  }
  return zaiInstance;
}

const server = http.createServer((req, res) => {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // Health check
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', calls: callCount, errors: errorCount, zai_ready: !!zaiInstance }));
    return;
  }

  // Stats
  if (req.method === 'GET' && req.url === '/stats') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ calls: callCount, errors: errorCount, zai_ready: !!zaiInstance }));
    return;
  }

  // Chat completion endpoint
  if (req.method === 'POST' && req.url === '/v1/chat') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const p = JSON.parse(body);
        callCount++;
        process.stderr.write(`[zai-bridge] #${callCount} node=${p.node_name || '?'} variant=${p.variant || '?'}\n`);

        const zai = await initZAI();
        const baseSystem = SYSTEM_PROMPTS[p.node_name] || 'Process this input and provide a clear, structured response.';
        const system = baseSystem + (p.variant ? ` [Variant: ${p.variant}]` : '') + (p.complexity ? ` [Complexity: ${p.complexity}]` : '');

        const completion = await zai.chat.completions.create({
          messages: [
            { role: 'system', content: system },
            { role: 'user', content: String(p.prompt || '') },
          ],
          temperature: p.temperature || 0.1,
          max_tokens: p.max_tokens || 500,
        });

        const content = completion.choices?.[0]?.message?.content || '';
        const usage = completion.usage || {};

        process.stderr.write(`[zai-bridge] #${callCount} response: ${content.substring(0, 80)}\n`);

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          content: content,
          model: completion.model || 'zai',
          usage: {
            prompt_tokens: usage.prompt_tokens || 0,
            completion_tokens: usage.completion_tokens || 0,
            total_tokens: usage.total_tokens || 0,
          },
          call_id: callCount,
        }));
      } catch (e) {
        errorCount++;
        process.stderr.write(`[zai-bridge] Error #${errorCount}: ${e.message}\n`);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message, content: null }));
      }
    });
    return;
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found. Use POST /v1/chat or GET /health' }));
});

// Graceful shutdown
function shutdown() {
  process.stderr.write('[zai-bridge] Shutting down...\n');
  server.close();
  process.exit(0);
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

// Start
initZAI().then(() => {
  server.listen(PORT, HOST, () => {
    process.stderr.write(`[zai-bridge] HTTP server running on http://${HOST}:${PORT}\n`);
    process.stderr.write(`[zai-bridge] Endpoints: POST /v1/chat, GET /health, GET /stats\n`);
  });
}).catch(e => {
  process.stderr.write(`[zai-bridge] Fatal: ${e.message}\n`);
  process.exit(1);
});
