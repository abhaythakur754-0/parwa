#!/usr/bin/env node
/**
 * PARWA LLM Bridge — Persistent HTTP server with ZAI SDK (primary) + Google Gemini (fallback).
 *
 * Python PARWA pipeline sends POST /v1/chat with prompt + node_name,
 * this server calls ZAI SDK first, falls back to Google Gemini API.
 *
 * Usage: node scripts/start-bridge.js
 * Bridge runs on port 4789 (override with ZAI_BRIDGE_PORT env var)
 */

const http = require('http');
const https = require('https');
const ZAI = require('z-ai-web-dev-sdk').default;

const PORT = parseInt(process.env.ZAI_BRIDGE_PORT || '4789', 10);
const HOST = '127.0.0.1';
const GOOGLE_AI_KEY = process.env.GOOGLE_AI_KEY || 'AIzaSyATHbcolmlaNufj6ZHR6tebMmlqqcmCsEs';
const GOOGLE_AI_HOST = 'generativelanguage.googleapis.com';

let zaiInstance = null;
let callCount = 0;
let errorCount = 0;
let googleDisabled = false;

// System prompts per node
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
    process.stderr.write('[parwa-bridge] ZAI SDK initialized (primary)\n');
  }
  return zaiInstance;
}

function callGemini(systemPrompt, userPrompt, options = {}) {
  return new Promise((resolve, reject) => {
    if (googleDisabled) return reject(new Error('Google AI disabled (region not supported)'));
    const model = options.model || 'gemini-2.0-flash-lite';
    const maxTokens = options.max_tokens || 500;
    const temperature = options.temperature || 0.1;
    const payload = {
      contents: [{ role: 'user', parts: [{ text: userPrompt }] }],
      generationConfig: { temperature, maxOutputTokens: maxTokens },
    };
    if (systemPrompt) payload.systemInstruction = { parts: [{ text: systemPrompt }] };
    const payloadStr = JSON.stringify(payload);
    const req = https.request({
      hostname: GOOGLE_AI_HOST, port: 443,
      path: `/v1beta/models/${model}:generateContent?key=${GOOGLE_AI_KEY}`,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payloadStr) },
    }, (res) => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        if (res.statusCode === 200) {
          try {
            const parsed = JSON.parse(data);
            const candidates = parsed.candidates || [];
            let content = '';
            if (candidates.length > 0) content = (candidates[0].content?.parts || []).map(p => p.text || '').join('');
            const u = parsed.usageMetadata || {};
            resolve({ content, model: `google/${model}`, usage: { prompt_tokens: u.promptTokenCount || 0, completion_tokens: u.candidatesTokenCount || 0, total_tokens: u.totalTokenCount || 0 } });
          } catch (e) { reject(e); }
        } else if (res.statusCode === 400 && data.includes('location')) {
          googleDisabled = true;
          reject(new Error('Google AI: region not supported — disabled'));
        } else if (res.statusCode === 429) {
          reject(new Error('Google Gemini rate limited (429)'));
        } else {
          reject(new Error(`Gemini API ${res.statusCode}: ${data.substring(0, 200)}`));
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(60000, () => { req.destroy(); reject(new Error('Gemini timeout')); });
    req.write(payloadStr);
    req.end();
  });
}

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', calls: callCount, errors: errorCount, primary: 'zai-sdk', fallback: googleDisabled ? 'disabled' : 'google-gemini' }));
    return;
  }

  if (req.method === 'GET' && req.url === '/stats') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ calls: callCount, errors: errorCount, zai_ready: !!zaiInstance, google_available: !googleDisabled }));
    return;
  }

  if (req.method === 'POST' && req.url === '/v1/chat') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const p = JSON.parse(body);
        callCount++;
        process.stderr.write(`[parwa-bridge] #${callCount} node=${p.node_name || '?'} variant=${p.variant || '?'}\n`);

        const baseSystem = SYSTEM_PROMPTS[p.node_name] || 'Process this input and provide a clear, structured response.';
        const system = baseSystem + (p.variant ? ` [Variant: ${p.variant}]` : '') + (p.complexity ? ` [Complexity: ${p.complexity}]` : '');

        // Try ZAI SDK first (primary)
        try {
          const zai = await initZAI();
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
          process.stderr.write(`[parwa-bridge] #${callCount} [zai] response: ${content.substring(0, 80)}\n`);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ content, model: completion.model || 'zai', usage: { prompt_tokens: usage.prompt_tokens || 0, completion_tokens: usage.completion_tokens || 0, total_tokens: usage.total_tokens || 0 }, call_id: callCount, backend: 'zai-sdk' }));
          return;
        } catch (zaiErr) {
          process.stderr.write(`[parwa-bridge] ZAI SDK failed: ${zaiErr.message} — trying Google Gemini\n`);
        }

        // Fallback: Google Gemini
        try {
          const result = await callGemini(system, String(p.prompt || ''), {
            temperature: p.temperature || 0.1,
            max_tokens: p.max_tokens || 500,
          });
          process.stderr.write(`[parwa-bridge] #${callCount} [gemini] response: ${result.content.substring(0, 80)}\n`);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ content: result.content, model: result.model, usage: result.usage, call_id: callCount, backend: 'google-gemini' }));
        } catch (geminiErr) {
          errorCount++;
          process.stderr.write(`[parwa-bridge] Error #${errorCount}: Both backends failed. Gemini: ${geminiErr.message}\n`);
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: `Both backends failed. ZAI: unavailable. Gemini: ${geminiErr.message}`, content: null }));
        }
      } catch (e) {
        errorCount++;
        process.stderr.write(`[parwa-bridge] Error #${errorCount}: ${e.message}\n`);
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
  process.stderr.write('[parwa-bridge] Shutting down...\n');
  server.close();
  process.exit(0);
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

// Start
process.stderr.write(`[parwa-bridge] Starting — Primary: ZAI SDK | Fallback: Google Gemini API\n`);
initZAI().then(() => {
  server.listen(PORT, HOST, () => {
    process.stderr.write(`[parwa-bridge] HTTP server running on http://${HOST}:${PORT}\n`);
    process.stderr.write(`[parwa-bridge] Endpoints: POST /v1/chat, GET /health, GET /stats\n`);
  });
}).catch(e => {
  process.stderr.write(`[parwa-bridge] Warning: ZAI init failed: ${e.message} — will use Google Gemini fallback\n`);
  server.listen(PORT, HOST, () => {
    process.stderr.write(`[parwa-bridge] HTTP server running on http://${HOST}:${PORT} (ZAI unavailable, Gemini only)\n`);
  });
});
