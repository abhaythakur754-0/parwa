#!/usr/bin/env node
/**
 * ZAI SDK Helper Script for PARWA LLM Pipeline
 *
 * Called via subprocess from Python (zai_llm.py).
 * Reads JSON from stdin, calls the ZAI SDK for each prompt, writes JSON to stdout.
 *
 * Input format (stdin JSON):
 *   [
 *     {
 *       "id": "unique-id",
 *       "messages": [
 *         {"role": "system", "content": "..."},
 *         {"role": "user", "content": "..."}
 *       ],
 *       "temperature": 0.1,
 *       "max_tokens": 500
 *     },
 *     ...
 *   ]
 *
 * Output format (stdout JSON):
 *   [
 *     {
 *       "id": "unique-id",
 *       "content": "response text",
 *       "model": "zai/default",
 *       "usage": {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N},
 *       "error": null  // or error message string if this item failed
 *     },
 *     ...
 *   ]
 */

import ZAI from 'z-ai-web-dev-sdk';

// Delay helper for rate-limit-friendly batching
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function processSinglePrompt(zai, item, maxRetries = 3) {
  const { id, messages, temperature = 0.1, max_tokens = 500 } = item;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const completion = await zai.chat.completions.create({
        messages: messages,
        temperature: temperature,
        max_tokens: max_tokens,
      });

      const content = completion.choices?.[0]?.message?.content ?? '';
      const usage = completion.usage ?? {
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0,
      };
      const model = completion.model ?? 'zai/default';

      return {
        id,
        content,
        model: `zai/${model}`,
        usage: {
          prompt_tokens: usage.prompt_tokens ?? 0,
          completion_tokens: usage.completion_tokens ?? 0,
          total_tokens: usage.total_tokens ?? 0,
        },
        error: null,
      };
    } catch (err) {
      const errMsg = err.message || String(err);
      // If rate limited (429), wait and retry with exponential backoff
      if (errMsg.includes('429') || errMsg.includes('Too many requests')) {
        if (attempt < maxRetries) {
          const backoffMs = 2000 * Math.pow(2, attempt); // 2s, 4s, 8s
          await delay(backoffMs);
          continue;
        }
      }
      // Non-retryable error or max retries exceeded
      return {
        id,
        content: '',
        model: 'zai/failed',
        usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
        error: errMsg,
      };
    }
  }
}

async function main() {
  // Read all stdin
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  const inputText = Buffer.concat(chunks).toString('utf-8');

  let prompts;
  try {
    prompts = JSON.parse(inputText);
  } catch (parseErr) {
    // If we can't parse input, write error array and exit
    const output = JSON.stringify([
      {
        id: 'parse-error',
        content: '',
        model: 'zai/failed',
        usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
        error: `Failed to parse stdin JSON: ${parseErr.message}`,
      },
    ]);
    process.stdout.write(output);
    process.exit(1);
  }

  if (!Array.isArray(prompts) || prompts.length === 0) {
    const output = JSON.stringify([
      {
        id: 'empty-input',
        content: '',
        model: 'zai/failed',
        usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
        error: 'Input must be a non-empty JSON array of prompt objects',
      },
    ]);
    process.stdout.write(output);
    process.exit(1);
  }

  // Initialize ZAI SDK
  let zai;
  try {
    zai = await ZAI.create();
  } catch (initErr) {
    // SDK init failed — return error for all prompts
    const results = prompts.map((p) => ({
      id: p.id ?? 'unknown',
      content: '',
      model: 'zai/failed',
      usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
      error: `ZAI SDK initialization failed: ${initErr.message || String(initErr)}`,
    }));
    process.stdout.write(JSON.stringify(results));
    process.exit(1);
  }

  // Process prompts sequentially with a small delay between them
  // to maximize TPM without hitting rate limits
  const results = [];
  const INTER_PROMPT_DELAY_MS = 500; // 500ms between calls for better rate limit compliance

  for (let i = 0; i < prompts.length; i++) {
    if (i > 0) {
      await delay(INTER_PROMPT_DELAY_MS);
    }
    const result = await processSinglePrompt(zai, prompts[i]);
    results.push(result);
  }

  // Write results to stdout
  process.stdout.write(JSON.stringify(results));
}

main().catch((err) => {
  // Unhandled error — write error output
  const output = JSON.stringify([
    {
      id: 'fatal-error',
      content: '',
      model: 'zai/failed',
      usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
      error: `Fatal error: ${err.message || String(err)}`,
    },
  ]);
  process.stdout.write(output);
  process.exit(1);
});
