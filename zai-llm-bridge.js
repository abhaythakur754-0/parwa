#!/usr/bin/env node
/**
 * ZAI LLM Bridge — HTTP server that wraps z-ai-web-dev-sdk for Python.
 *
 * Python PARWA pipeline sends POST /v1/chat with messages,
 * this server calls zai SDK chat.completions.create() and returns the response.
 *
 * Usage: node zai-llm-bridge.js [--port 4789]
 */

const http = require('http');
const ZAI = require('z-ai-web-dev-sdk').default;

const PORT = parseInt(process.env.ZAI_BRIDGE_PORT || '4789', 10);

let zaiInstance = null;
let callCount = 0;
let errorCount = 0;

async function initZAI() {
  if (!zaiInstance) {
    zaiInstance = await ZAI.create();
    console.log('[zai-bridge] ZAI SDK initialized');
  }
  return zaiInstance;
}

/**
 * Build the system+user messages based on node context.
 * This replaces the MockLLM's keyword matching with real AI reasoning.
 */
function buildMessages(body) {
  const { prompt, node_name, variant, complexity, ticket_id } = body;

  // Default system prompt — tell the AI what role it's playing
  let system = 'You are PARWA, an AI customer support system. ';

  // Node-specific system instructions for structured output
  switch (node_name) {
    case 'INTENT_CLASSIFIER':
      system += 'Classify this customer message into ONE intent: order_status, refund_request, cancellation, billing_issue, technical_support, faq_question, complaint, account_modification, escalation, general_inquiry. Reply with ONLY: intent|confidence (e.g. refund_request|0.95)';
      break;
    case 'SENTIMENT_ANALYZER':
      system += 'Analyze the sentiment of this customer message. Reply with ONLY: sentiment|urgency (e.g. frustrated|0.8) where sentiment is one of: happy, neutral, frustrated, angry. Urgency is 0.0-1.0.';
      break;
    case 'ESCALATION_DECISION':
      system += 'Should this ticket be escalated to a human agent? Reply with ONLY: true|reason or false| where reason is one of: legal_threat, high_urgency, complex_technical, vip_customer, angry_customer_with_critical_issue';
      break;
    case 'FAQ_MATCHER':
      system += 'Does this message match any FAQ? Reply with ONLY: faq_id|relevance_score|content or no_match|0.00| where relevance is 0.0-1.0. Common FAQs: refund_policy, shipping_faq, return_policy, billing_faq, account_faq';
      break;
    case 'KB_RETRIEVER':
      system += 'Retrieve relevant knowledge base information for this query. Provide a helpful, factual answer based on common customer support policies.';
      break;
    case 'INTEGRATION_LOOKUP':
      system += 'Look up CRM data for this customer. Reply with a JSON object containing order_id, status, charges array, and customer info. Use realistic data.';
      break;
    case 'REASONING_ENGINE':
      system += 'Think step-by-step about this customer issue. Provide a clear reasoning chain ending with: Conclusion: <your conclusion>';
      break;
    case 'REVERSE_THINKER':
      system += 'Work backward from the desired outcome. Start with "Goal: <outcome>" then trace back through requirements. End with "Validation: PASSED/FAILED".';
      break;
    case 'TREE_OF_THOUGHTS':
      system += 'Explore 3 different solution paths. For each path provide: Path N: <description> (confidence: 0.XX, selected: true/false). Select the best path.';
      break;
    case 'STRATEGY_PLANNER':
      system += 'Create a step-by-step strategy plan. Number each step. Be specific about actions and evidence needed.';
      break;
    case 'ACTION_PLANNER':
      system += 'Plan the specific actions needed. Each action should have: action_type, description, risk_level. Valid action types: send_reply, process_refund, cancel_order, modify_account, escalate_to_human, share_faq, share_policy, create_note';
      break;
    case 'PROACTIVE_CHECKER':
      system += 'What proactive follow-ups or predictions can we make? Suggest 1-2 insights with type (follow_up, prediction, cross_sell), description, and confidence.';
      break;
    case 'PREDICTION_ENGINE':
      system += 'Predict what might happen next with this customer. Consider churn risk, upsell opportunities. Reply with prediction description and confidence.';
      break;
    case 'QUALITY_SCORER':
      system += 'Score the quality of this customer service response on a scale of 0-100. Reply with ONLY: score|issues where issues are comma-separated quality concerns (e.g. 85|accurate,complete,compliant or 45|incomplete,not_empathetic)';
      break;
    case 'PII_COMPLIANCE_GUARD':
      system += 'Check this message for PII (SSN, credit card, email, phone, address). Reply with ONLY: true|details or false|No PII detected where details describe what PII was found.';
      break;
    case 'RESPONSE_FORMATTER':
      system += 'Format a professional, empathetic customer service response. Be concise but thorough. Include specific details from the evidence.';
      break;
    default:
      system += 'Process this input and provide a clear, structured response.';
  }

  if (variant) {
    system += ` [Variant: ${variant}]`;
  }
  if (complexity) {
    system += ` [Complexity: ${complexity}]`;
  }

  const messages = [
    { role: 'system', content: system },
    { role: 'user', content: String(prompt || '') },
  ];

  return messages;
}

const server = http.createServer(async (req, res) => {
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
    res.end(JSON.stringify({ status: 'ok', calls: callCount, errors: errorCount }));
    return;
  }

  // Stats
  if (req.method === 'GET' && req.url === '/stats') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ calls: callCount, errors: errorCount, zai_ready: !!zaiInstance }));
    return;
  }

  // Chat completion endpoint
  if (req.method === 'POST' && (req.url === '/v1/chat' || req.url === '/chat')) {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const parsed = JSON.parse(body);
        callCount++;

        const zai = await initZAI();
        const messages = buildMessages(parsed);

        const completion = await zai.chat.completions.create({
          messages: messages,
          temperature: parsed.temperature || 0.1,
          max_tokens: parsed.max_tokens || 500,
        });

        const content = completion.choices?.[0]?.message?.content || '';
        const usage = completion.usage || {};

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          content: content,
          model: completion.model || 'zai-unknown',
          usage: {
            prompt_tokens: usage.prompt_tokens || 0,
            completion_tokens: usage.completion_tokens || 0,
            total_tokens: usage.total_tokens || 0,
          },
          call_id: callCount,
        }));
      } catch (e) {
        errorCount++;
        console.error('[zai-bridge] Error:', e.message);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message, content: null }));
      }
    });
    return;
  }

  // Raw messages endpoint (pass messages directly)
  if (req.method === 'POST' && req.url === '/v1/chat/raw') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const parsed = JSON.parse(body);
        callCount++;

        const zai = await initZAI();
        const messages = parsed.messages || [];

        const completion = await zai.chat.completions.create({
          messages: messages,
          temperature: parsed.temperature || 0.1,
          max_tokens: parsed.max_tokens || 500,
        });

        const content = completion.choices?.[0]?.message?.content || '';
        const usage = completion.usage || {};

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          content: content,
          model: completion.model || 'zai-unknown',
          usage: {
            prompt_tokens: usage.prompt_tokens || 0,
            completion_tokens: usage.completion_tokens || 0,
            total_tokens: usage.total_tokens || 0,
          },
          call_id: callCount,
        }));
      } catch (e) {
        errorCount++;
        console.error('[zai-bridge] Raw error:', e.message);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message, content: null }));
      }
    });
    return;
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found. Use POST /v1/chat or /v1/chat/raw' }));
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[zai-bridge] HTTP server running on http://127.0.0.1:${PORT}`);
  console.log(`[zai-bridge] Endpoints: POST /v1/chat, POST /v1/chat/raw, GET /health, GET /stats`);
  // Pre-initialize ZAI SDK
  initZAI().then(() => console.log('[zai-bridge] Ready for requests'));
});
