/**
 * LLM shim — bridges the PARWA pipeline (Python) to the built-in Z.ai LLM.
 * LOCAL TEST ONLY (sandbox pipeline verification).
 *
 * POST /v1/chat/completions
 *   body: { messages: [{role, content}...], max_tokens?, temperature? }
 *   resp: { content: "..." }
 */
import ZAI from "z-ai-web-dev-sdk";

const PORT = 3077;
let zai: any = null;

async function getZAI() {
  if (!zai) zai = await ZAI.create();
  return zai;
}

const server = Bun.serve({
  port: PORT,
  async fetch(req) {
    const url = new URL(req.url);
    if (req.method === "GET" && url.pathname === "/health") {
      return Response.json({ ok: true });
    }
    if (req.method !== "POST" || url.pathname !== "/v1/chat/completions") {
      return Response.json({ error: "not found" }, { status: 404 });
    }
    try {
      const body = await req.json();
      const messages = Array.isArray(body.messages) ? body.messages : [];
      const z = await getZAI();
      const completion = await z.chat.completions.create({
        messages,
        thinking: { type: "disabled" },
      });
      const content = completion?.choices?.[0]?.message?.content ?? "";
      return Response.json({ content });
    } catch (err: any) {
      console.error("[llm-shim] error:", err?.message || err);
      return Response.json({ error: String(err?.message || err) }, { status: 500 });
    }
  },
});

console.log(`[llm-shim] listening on http://127.0.0.1:${PORT} (Z.ai brain)`);
