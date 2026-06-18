/**
 * PARWA LLM Proxy — Persistent z-ai SDK server
 *
 * Starts once via bun, handles multiple LLM calls via stdin/stdout.
 * Eliminates "Initializing Z-AI SDK..." overhead per call.
 * Rate limits: 4s between calls, 5/10/15s retry backoff on 429.
 *
 * Protocol (newline-delimited JSON):
 *   IN:  {"id": "1", "prompt": "...", "max_tokens": 256, "temperature": 0.3}
 *   OUT: {"id": "1", "content": "...", "model": "...", "tokens": 42, "error": null}
 *
 * Usage: bun llm_proxy.js
 */

import ZAI from 'z-ai-web-dev-sdk';
import { createInterface } from 'readline';

let zai = null;
let callCount = 0;
let totalTokens = 0;
let lastCallTime = 0;
const MIN_CALL_INTERVAL_MS = 6000; // 6s between calls = ~10 calls/min (safe under z-ai rate limit)

async function init() {
  zai = await ZAI.create();
  const rl = createInterface({ input: process.stdin });

  process.stderr.write('LLM_PROXY_READY\n');

  for await (const line of rl) {
    if (!line.trim()) continue;
    try {
      const req = JSON.parse(line);
      await handleRequest(req);
    } catch (e) {
      const errResp = { id: 'parse_error', content: '', model: '', tokens: 0, error: e.message };
      process.stdout.write(JSON.stringify(errResp) + '\n');
    }
  }
}

async function handleRequest(req) {
  const { id, prompt } = req;
  callCount++;

  const maxRetries = 4;
  let lastError = null;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      // Enforce minimum interval between calls
      const now = Date.now();
      const elapsed = now - lastCallTime;
      if (lastCallTime > 0 && elapsed < MIN_CALL_INTERVAL_MS) {
        const waitMs = MIN_CALL_INTERVAL_MS - elapsed + 500;
        process.stderr.write(`LLM_PROXY_THROTTLE: id=${id} wait=${waitMs}ms\n`);
        await new Promise(r => setTimeout(r, waitMs));
      }

      // Extra backoff on retries (10s, 20s, 30s, 40s)
      if (attempt > 1) {
        const waitMs = 10000 * attempt;
        process.stderr.write(`LLM_PROXY_RETRY: id=${id} attempt=${attempt} wait=${waitMs}ms\n`);
        await new Promise(r => setTimeout(r, waitMs));
      }

      const messages = [{ role: 'user', content: prompt }];

      const completion = await zai.chat.completions.create({
        messages,
        thinking: { type: 'disabled' },
      });

      lastCallTime = Date.now();
      const content = completion.choices?.[0]?.message?.content || '';
      const model = completion.model || 'unknown';
      const tokens = completion.usage?.total_tokens || 0;
      totalTokens += tokens;

      const resp = { id, content: content.trim(), model, tokens, error: null };
      process.stdout.write(JSON.stringify(resp) + '\n');

      if (callCount % 5 === 0) {
        process.stderr.write(`LLM_PROXY_STATS: calls=${callCount} tokens=${totalTokens} model=${model}\n`);
      }
      return;
    } catch (e) {
      lastError = e;
      const isRateLimit = e.message?.includes('429');
      if (!isRateLimit || attempt === maxRetries) {
        break;
      }
    }
  }

  const resp = { id, content: '', model: '', tokens: 0, error: lastError?.message || 'unknown' };
  process.stdout.write(JSON.stringify(resp) + '\n');
  process.stderr.write(`LLM_PROXY_ERROR: id=${id} error=${lastError?.message}\n`);
}

init().catch(e => {
  process.stderr.write(`LLM_PROXY_FATAL: ${e.message}\n`);
  process.exit(1);
});