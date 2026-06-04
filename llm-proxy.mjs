/**
 * Standalone LLM Proxy Server using ZAI SDK
 *
 * This runs as a separate Node.js process alongside the Python backend.
 * It provides an OpenAI-compatible /chat/completions endpoint that the
 * Python llm_gateway.py (ZAI_GATEWAY mode) calls.
 *
 * Usage: node llm-proxy.mjs
 * Default port: 3001 (avoids conflict with Next.js on 3000)
 */

import http from 'http';
import { config } from 'dotenv';
import { createRequire } from 'module';

// Load .env file
config({ path: '.env' });

const require = createRequire(import.meta.url);
let ZAI = null;
try {
  ZAI = require('z-ai-web-dev-sdk').default || require('z-ai-web-dev-sdk');
} catch (e) {
  console.warn('[LLM Proxy] z-ai-web-dev-sdk not found via require, trying import...');
}

const PORT = parseInt(process.env.LLM_PROXY_PORT || '3001', 10);
const API_KEY = process.env.ZAI_API_KEY || ''; // Optional auth

let zaiInstance = null;

async function getZAI() {
  if (!zaiInstance) {
    try {
      let ZAIClass = ZAI;
      if (!ZAIClass) {
        const mod = await import('z-ai-web-dev-sdk');
        ZAIClass = mod.default || mod;
      }
      if (ZAIClass && typeof ZAIClass.create === 'function') {
        zaiInstance = await ZAIClass.create();
        console.log('[LLM Proxy] ZAI SDK initialized successfully');
      } else {
        console.error('[LLM Proxy] ZAI SDK has no create() method');
      }
    } catch (err) {
      console.error('[LLM Proxy] ZAI SDK init failed:', err.message?.slice(0, 200));
    }
  }
  return zaiInstance;
}

// Initialize on startup
getZAI();

// Prevent crashes from unhandled rejections
process.on('unhandledRejection', (err) => {
  console.error('[LLM Proxy] Unhandled rejection:', err?.message?.slice(0, 200));
});
process.on('uncaughtException', (err) => {
  console.error('[LLM Proxy] Uncaught exception:', err?.message?.slice(0, 200));
});

async function callZAI(messages, max_tokens, temperature) {
  try {
    const zai = await getZAI();
    if (!zai?.chat?.completions) return null;

    const completion = await zai.chat.completions.create({
      messages: messages.map(m => ({
        role: m.role,
        content: m.content,
      })),
      temperature,
      max_tokens,
    });

    const text = completion?.choices?.[0]?.message?.content;
    if (text && text.trim().length > 0) {
      return {
        text: text.trim(),
        model: completion?.model || 'zai-default',
        tokens: completion?.usage?.total_tokens || 0,
      };
    }
    return null;
  } catch (err) {
    console.warn('[LLM Proxy] ZAI SDK call failed:', err.message?.slice(0, 200));
    return null;
  }
}

// Fallback providers (optional, used if ZAI SDK fails)
async function callGoogleAI(messages, max_tokens, temperature) {
  const key = process.env.GOOGLE_AI_API_KEY;
  if (!key) return null;
  try {
    const systemMsg = messages.find(m => m.role === 'system');
    const chatMsgs = messages.filter(m => m.role !== 'system');
    const contents = chatMsgs.map(m => ({
      role: m.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: m.content }],
    }));

    const resp = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${key}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          systemInstruction: systemMsg ? { parts: [{ text: systemMsg.content }] } : undefined,
          contents,
          generationConfig: { temperature, maxOutputTokens: max_tokens },
        }),
        signal: AbortSignal.timeout(30000),
      }
    );

    if (!resp.ok) return null;
    const data = await resp.json();
    const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (text && text.trim()) {
      return { text: text.trim(), model: 'gemini-2.0-flash', tokens: data?.usageMetadata?.totalTokenCount || 0 };
    }
    return null;
  } catch (err) {
    console.warn('[LLM Proxy] Google AI failed:', err.message?.slice(0, 100));
    return null;
  }
}

async function callGroq(messages, max_tokens, temperature) {
  const key = process.env.GROQ_API_KEY;
  if (!key) return null;
  try {
    const resp = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${key}` },
      body: JSON.stringify({ model: 'llama-3.3-70b-versatile', messages, temperature, max_tokens }),
      signal: AbortSignal.timeout(30000),
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    const text = data?.choices?.[0]?.message?.content;
    if (text && text.trim()) {
      return { text: text.trim(), model: data?.model || 'llama-3.3-70b-versatile', tokens: data?.usage?.total_tokens || 0 };
    }
    return null;
  } catch (err) {
    console.warn('[LLM Proxy] Groq failed:', err.message?.slice(0, 100));
    return null;
  }
}

async function callCerebras(messages, max_tokens, temperature) {
  const key = process.env.CEREBRAS_API_KEY;
  if (!key) return null;
  try {
    const resp = await fetch('https://api.cerebras.ai/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${key}` },
      body: JSON.stringify({ model: 'llama-4-scout-17b-16e-instruct', messages, temperature, max_tokens }),
      signal: AbortSignal.timeout(30000),
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    const text = data?.choices?.[0]?.message?.content;
    if (text && text.trim()) {
      return { text: text.trim(), model: data?.model || 'llama-4-scout', tokens: data?.usage?.total_tokens || 0 };
    }
    return null;
  } catch (err) {
    console.warn('[LLM Proxy] Cerebras failed:', err.message?.slice(0, 100));
    return null;
  }
}

// Smart Router
async function getLLMResponse(messages, max_tokens, temperature) {
  const zaiResult = await callZAI(messages, max_tokens, temperature);
  if (zaiResult) return zaiResult;

  const googleResult = await callGoogleAI(messages, max_tokens, temperature);
  if (googleResult) return googleResult;

  const groqResult = await callGroq(messages, max_tokens, temperature);
  if (groqResult) return groqResult;

  const cerebrasResult = await callCerebras(messages, max_tokens, temperature);
  if (cerebrasResult) return cerebrasResult;

  return null;
}

// HTTP Server
const server = http.createServer(async (req, res) => {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // Health check
  if (req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      service: 'parwa-llm-proxy',
      version: '1.0.0',
      zai_sdk: zaiInstance ? 'initialized' : 'not_initialized',
      providers: [
        { name: 'zai_sdk', priority: 1, status: zaiInstance ? 'available' : 'unavailable' },
        { name: 'google_ai', priority: 2, status: process.env.GOOGLE_AI_API_KEY ? 'configured' : 'not_configured' },
        { name: 'groq', priority: 3, status: process.env.GROQ_API_KEY ? 'configured' : 'not_configured' },
        { name: 'cerebras', priority: 4, status: process.env.CEREBRAS_API_KEY ? 'configured' : 'not_configured' },
      ],
    }, null, 2));
    return;
  }

  // Chat completions
  if (req.method === 'POST') {
    try {
      // Optional auth check
      if (API_KEY) {
        const authHeader = req.headers['authorization'];
        if (!authHeader || !authHeader.startsWith('Bearer ') || authHeader.slice(7) !== API_KEY) {
          res.writeHead(401, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: { message: 'Invalid API key', type: 'auth_error' } }));
          return;
        }
      }

      let body = '';
      for await (const chunk of req) body += chunk;
      const { model, messages, max_tokens = 300, temperature = 0.5 } = JSON.parse(body);

      if (!messages || !Array.isArray(messages) || messages.length === 0) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: { message: 'messages is required', type: 'invalid_request' } }));
        return;
      }

      const result = await getLLMResponse(messages, max_tokens, temperature);

      if (!result) {
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: { message: 'All LLM providers unavailable', type: 'server_error' } }));
        return;
      }

      const responseId = `chatcmpl-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        id: responseId,
        object: 'chat.completion',
        created: Math.floor(Date.now() / 1000),
        model: result.model,
        choices: [{
          index: 0,
          message: { role: 'assistant', content: result.text },
          finish_reason: 'stop',
        }],
        usage: {
          prompt_tokens: 0,
          completion_tokens: 0,
          total_tokens: result.tokens,
        },
      }));
    } catch (err) {
      console.error('[LLM Proxy] Error:', err.message);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: { message: 'Internal server error', type: 'server_error' } }));
    }
    return;
  }

  res.writeHead(404);
  res.end('Not found');
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[LLM Proxy] Server running on http://0.0.0.0:${PORT}`);
  console.log(`[LLM Proxy] Endpoints: GET / (health), POST /chat/completions`);
  console.log(`[LLM Proxy] ZAI SDK: ${zaiInstance ? 'ready' : 'initializing...'}`);
});
