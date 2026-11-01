/**
 * llm-shim — OpenAI-compatible /v1/chat/completions over z-ai-web-dev-sdk.
 *
 * Why: the PARWA Python pipeline speaks the OpenAI chat API (hardcoded
 * provider URLs, e.g. Groq). This sandbox has no Groq key but DOES have
 * the z-ai SDK. This shim translates one endpoint so llm_client.py can
 * point at it via GROQ_BASE_URL=http://127.0.0.1:3040/v1 and get REAL
 * AI answers. Port 3040 (fixed — mini service rule).
 *
 * Run: bun run dev   (bun --hot index.ts)
 */
import ZAI from "z-ai-web-dev-sdk";

const PORT = 3040;

let zaiInstance: any = null;
async function zai() {
  if (!zaiInstance) zaiInstance = await ZAI.create();
  return zaiInstance;
}

// Serialize all completions + keep a small gap between calls: the
// pipeline bursts many LLM calls and the z-ai API answers bursts with 429.
let chain: Promise<any> = Promise.resolve();
function serialized<T>(fn: () => Promise<T>): Promise<T> {
  const next = chain.then(fn, fn);
  chain = next.then(
    () => new Promise((r) => setTimeout(r, 300)),
    () => new Promise((r) => setTimeout(r, 300)),
  );
  return next;
}

const server = Bun.serve({
  port: PORT,
  idleTimeout: 255, // z-ai can be slow; keep the socket open
  async fetch(req) {
    const url = new URL(req.url);

    if (url.pathname === "/health") {
      return Response.json({ ok: true, service: "llm-shim" });
    }

    if (url.pathname.endsWith("/chat/completions") && req.method === "POST") {
      try {
        const body: any = await req.json();
        const messages = Array.isArray(body?.messages) ? body.messages : [];
        if (!messages.length) {
          return Response.json(
            { error: { message: "messages required" } },
            { status: 400 },
          );
        }
        const client = await zai();
        // Serialized + retry with backoff on 429/5xx — the pipeline fires
        // LLM calls back-to-back (node_4 makes 9, node_8 another 7) and
        // the z-ai API rate-limits bursts. llm_client's HTTP timeout is
        // env-raised (LLM_HTTP_TIMEOUT) so these waits are survivable.
        const content: string = await serialized(async () => {
          let lastErr: any = null;
          for (let attempt = 0; attempt < 7; attempt++) {
            try {
              const completion = await client.chat.completions.create({
                messages,
                thinking: { type: "disabled" },
              });
              return completion?.choices?.[0]?.message?.content ?? "";
            } catch (err: any) {
              lastErr = err;
              const msg = String(err?.message || err);
              if (!msg.includes("429") && !msg.includes("status 5")) throw err;
              await new Promise((r) => setTimeout(r, [5, 10, 15, 20, 20, 20, 20][attempt] * 1000));
            }
          }
          throw lastErr;
        });
        // OpenAI-shaped response — llm_client.py reads
        // choices[0].message.content
        return Response.json({
          id: "chatcmpl-shim-" + Date.now(),
          object: "chat.completion",
          model: body?.model || "z-ai",
          choices: [
            {
              index: 0,
              message: { role: "assistant", content },
              finish_reason: "stop",
            },
          ],
          usage: {
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0,
          },
        });
      } catch (err: any) {
        console.error("llm-shim error:", err?.message || err);
        return Response.json(
          { error: { message: String(err?.message || err) } },
          { status: 502 },
        );
      }
    }

    return Response.json({ error: { message: "not found" } }, { status: 404 });
  },
});

console.log(`llm-shim listening on http://127.0.0.1:${PORT}/v1/chat/completions`);
