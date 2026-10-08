/**
 * Mock Superglue server — LOCAL TEST ONLY (sandbox pipeline verification).
 *
 * Mimics the real Superglue API surface used by backend/app/core/superglue_client.py:
 *   GET  /sgapi/v1/tools              → { data: [tool...] }
 *   GET  /sgapi/v1/tools/:id          → tool or 404
 *   POST /sgapi/v1/tools              → 201 created tool
 *   POST /sgapi/v1/tools/:id/run      → { status:"success", data, runId, stepResults }
 *   POST /sgapi/v1/tools/run          → same (inline-config fallback shape)
 *   POST /sgapi/v1/runs               → 202 (run logging)
 *
 * Every /run call is appended to /tmp/mock-superglue-runs.jsonl so the
 * pipeline harness can PROVE the agent executed the tool on its own.
 */
const PORT = 3076;
const RUNS_LOG = "/tmp/mock-superglue-runs.jsonl";

const tools = new Map();

function seed() {
  tools.set("payment-refund-by-email", {
    id: "payment-refund-by-email",
    name: "payment-refund-by-email",
    description: "Issue a full or partial refund for a customer identified by email",
    instruction: "Refunds the given amount to the customer found by email via the payment provider.",
    inputSchema: {
      type: "object",
      properties: {
        customerEmail: { type: "string" },
        amount: { type: "number" },
        reason: { type: "string" },
      },
      required: ["customerEmail"],
    },
    archived: false,
    steps: [
      { stepId: "lookup", name: "find customer" },
      { stepId: "refund", name: "issue refund" },
    ],
  });
  tools.set("customer-lookup-by-email", {
    id: "customer-lookup-by-email",
    name: "customer-lookup-by-email",
    description: "Look up a customer profile by email",
    instruction: "Returns the customer record for the given email.",
    inputSchema: { type: "object", properties: { customerEmail: { type: "string" } }, required: ["customerEmail"] },
    archived: false,
  });
}
seed();

function logRun(entry) {
  try {
    entry.ts = new Date().toISOString();
    require("fs").appendFileSync(RUNS_LOG, JSON.stringify(entry) + "\n");
  } catch {}
}

const server = Bun.serve({
  port: PORT,
  async fetch(req) {
    const url = new URL(req.url);
    const path = url.pathname;
    const method = req.method;

    // Auth check like the real stack (Bearer token required)
    const auth = req.headers.get("authorization") || "";
    if (!auth.startsWith("Bearer ") || auth.length < 10) {
      return Response.json({ success: false, error: "Authentication failed", message: "Authentication failed" }, { status: 401 });
    }

    // POST /sgapi/v1/tools/:id/run   (or /sgapi/v1/tools/run inline)
    if (method === "POST" && (path.match(/^\/sgapi\/v1\/tools\/([^/]+)\/run$/) || path === "/sgapi/v1/tools/run")) {
      let body = {};
      try { body = await req.json(); } catch {}
      const inputs = body.inputs || {};
      const inlineTool = body.tool;
      const rawId = inlineTool?.id || path.split("/")[4];
      const tool = resolveTool(rawId);
      const toolId = tool?.id || rawId;

      logRun({ kind: "run", toolId, inputs });

      if (toolId === "customer-lookup-by-email") {
        return Response.json({
          status: "success",
          runId: "run_lookup_" + Date.now(),
          data: { customer: { email: inputs.customerEmail, tier: "gold", orders: 14 } },
          stepResults: [{ stepId: "lookup", success: true, error: null }],
        });
      }
      if (toolId === "payment-refund-by-email") {
        const amount = Number(inputs.amount ?? 0);
        return Response.json({
          status: "success",
          runId: "run_refund_" + Date.now(),
          data: {
            refundId: "re_mock_" + Math.random().toString(36).slice(2, 10),
            status: "succeeded",
            amount: amount || 25.0,
            currency: "usd",
            customerEmail: inputs.customerEmail ?? "unknown",
            processedAt: new Date().toISOString(),
          },
          stepResults: [
            { stepId: "lookup", success: true, error: null },
            { stepId: "refund", success: true, error: null },
          ],
        });
      }
      // Generic created tool — echo success so the pipeline can proceed
      return Response.json({
        status: "success",
        runId: "run_generic_" + Date.now(),
        data: { ok: true, toolId, inputs },
        stepResults: [{ stepId: "step1", success: true, error: null }],
      });
    }

    // Namespacing: real Superglue stores tools as tenant_{tid}__{toolId}
    function resolveTool(rawId: string) {
      if (tools.has(rawId)) return tools.get(rawId);
      const m = rawId.match(/^tenant_.+?__(.+)$/);
      if (m && tools.has(m[1])) return tools.get(m[1]);
      return null;
    }

    // GET /sgapi/v1/tools/:id
    if (method === "GET" && path.match(/^\/sgapi\/v1\/tools\/[^/]+$/)) {
      const id = decodeURIComponent(path.split("/")[4]);
      const tool = resolveTool(id);
      if (!tool) return Response.json({ error: "tool not found" }, { status: 404 });
      return Response.json(tool);
    }

    // POST /sgapi/v1/tools (create — used by tool-forge)
    if (method === "POST" && path === "/sgapi/v1/tools") {
      let body = {};
      try { body = await req.json(); } catch {}
      const id = body.id || body.name || ("forged-" + Math.random().toString(36).slice(2, 8));
      const tool = { id, name: id, archived: false, inputSchema: body.inputSchema ?? {}, ...body, id };
      tools.set(id, tool);
      logRun({ kind: "create", toolId: id });
      return Response.json(tool, { status: 201 });
    }

    // GET /sgapi/v1/tools (list)
    if (method === "GET" && path === "/sgapi/v1/tools") {
      return Response.json({ data: [...tools.values()] });
    }

    // POST /sgapi/v1/runs (logging)
    if (method === "POST" && path === "/sgapi/v1/runs") {
      return Response.json({ accepted: true }, { status: 202 });
    }

    return Response.json({ error: "not found", path }, { status: 404 });
  },
});

console.log(`[mock-superglue] listening on http://127.0.0.1:${PORT} — runs logged to ${RUNS_LOG}`);
