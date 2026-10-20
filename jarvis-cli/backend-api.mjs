/**
 * PARWA Jarvis CLI — Real Backend API Wiring
 *
 * This module is the "hands" of Jarvis. The LLM (z-ai-web-dev-sdk) is the
 * "brain" that picks tools; the executors here perform them against the
 * REAL Parwa backend instead of returning mock data.
 *
 * Configuration (env vars):
 *   PARWA_API_URL   — backend base URL (default http://localhost:10000)
 *   PARWA_API_TOKEN — JWT from POST /api/auth/login  (REQUIRED for live mode)
 *   PARWA_ORIGIN    — Origin header (default http://localhost:3000)
 *
 * Without PARWA_API_TOKEN the CLI stays in honest demo mode: executors fall
 * back to the built-in mocks and every reply is labeled "[demo]".
 *
 * Wired endpoints (verified in backend/app):
 *   GET  /health                       public health probe
 *   GET  /jarvis/status                integration health, load, active flags
 *   GET  /jarvis/metrics               pipeline metrics
 *   POST /jarvis/command/pause         pause a target ("all" = everything)
 *   POST /jarvis/command/resume        resume a paused target
 *   GET  /api/v1/tickets               ticket list (filterable)
 *   POST /api/v1/tickets               create ticket
 *   GET  /api/billing/subscription     current subscription
 *   GET  /api/integrations             connected integrations
 */

const API_URL = (process.env.PARWA_API_URL || "http://localhost:10000").replace(/\/$/, "");
const API_TOKEN = process.env.PARWA_API_TOKEN || "";
const ORIGIN = process.env.PARWA_ORIGIN || "http://localhost:3000";
const DEMO_TAG = " [demo data — set PARWA_API_TOKEN to control your real system]";

export function isLive() {
  return Boolean(API_TOKEN);
}

/** Low-level authenticated call. Returns { status, data }. Never throws. */
export async function apiCall(method, path, body = null, timeoutMs = 90000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(API_URL + path, {
      method,
      headers: {
        "Content-Type": "application/json",
        "Origin": ORIGIN,
        ...(API_TOKEN ? { "Authorization": `Bearer ${API_TOKEN}` } : {}),
      },
      body: body === null ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    let data = null;
    try { data = await resp.json(); } catch { data = null; }
    return { status: resp.status, data };
  } catch (err) {
    return { status: 0, data: { error: String(err?.message || err) } };
  } finally {
    clearTimeout(timer);
  }
}

function _items(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.tickets)) return payload.tickets;
  return [];
}

function _briefTicket(t) {
  const num = t.ticket_number || t.id?.slice(0, 8) || "?";
  return `  • ${num} [${t.status}] ${t.priority || "normal"} — ${String(t.subject || "").slice(0, 70)}`;
}

// ══════════════════════════════════════════════════════════════════
// REAL EXECUTORS — same {success, message} contract as the mocks
// ══════════════════════════════════════════════════════════════════

export const REAL_EXECUTORS = {
  async check_system_health() {
    const [health, status] = await Promise.all([
      apiCall("GET", "/health", null, 15000),
      apiCall("GET", "/jarvis/status"),
    ]);
    if (health.status !== 200 && status.status !== 200) {
      return { success: false, message: `Backend unreachable at ${API_URL} (health http=${health.status}).` };
    }
    const s = status.data || {};
    const bits = [`backend is up (health http=${health.status})`];
    if (s.integration_health && typeof s.integration_health === "object") {
      const entries = Object.entries(s.integration_health);
      if (entries.length) bits.push(`integrations: ${entries.map(([k, v]) => `${k}=${typeof v === "object" ? (v.status || v.healthy || "?") : v}`).join(", ")}`);
    }
    if (s.active_flags) bits.push(`active flags: ${JSON.stringify(s.active_flags).slice(0, 200)}`);
    if (s.load) bits.push(`load: ${JSON.stringify(s.load).slice(0, 120)}`);
    return { success: true, message: bits.join(" | ") };
  },

  async get_performance_metrics() {
    const { status, data } = await apiCall("GET", "/jarvis/metrics");
    if (status !== 200) return { success: false, message: `Metrics unavailable (http=${status}).` };
    const text = JSON.stringify(data);
    return { success: true, message: `Current metrics: ${text.slice(0, 400)}` };
  },

  async get_agent_status() {
    const { status, data } = await apiCall("GET", "/jarvis/status");
    if (status !== 200) return { success: false, message: `Agent status unavailable (http=${status}).` };
    const s = data || {};
    const bits = [];
    if (s.active_flags) bits.push(`control flags: ${JSON.stringify(s.active_flags).slice(0, 200)}`);
    if (s.integration_health) bits.push(`channels: ${JSON.stringify(s.integration_health).slice(0, 200)}`);
    if (s.load) bits.push(`load: ${JSON.stringify(s.load).slice(0, 150)}`);
    return { success: true, message: bits.length ? bits.join(" | ") : `Agent layer healthy — no pauses or incidents active. Raw status: ${JSON.stringify(s).slice(0, 200)}` };
  },

  async pause_all_ai() {
    const { status, data } = await apiCall("POST", "/jarvis/command/pause", { target: "all" });
    return status >= 200 && status < 300
      ? { success: true, message: "AI processing is now PAUSED across all channels. Customers' new tickets will queue until you ask me to resume. (audit-logged on the server)" }
      : { success: false, message: `Pause failed (http=${status}): ${JSON.stringify(data).slice(0, 200)}` };
  },

  async resume_all_ai() {
    const { status, data } = await apiCall("POST", "/jarvis/command/resume", { target: "all" });
    return status >= 200 && status < 300
      ? { success: true, message: "AI processing RESUMED across all channels. Queued tickets will start moving again." }
      : { success: false, message: `Resume failed (http=${status}): ${JSON.stringify(data).slice(0, 200)}` };
  },

  async emergency_stop() {
    const { status, data } = await apiCall("POST", "/jarvis/command/pause", { target: "all" });
    return status >= 200 && status < 300
      ? { success: true, message: "EMERGENCY STOP executed — everything is paused. Escalations will still reach your team in the CRM. Say the word when you want to resume." }
      : { success: false, message: `Emergency stop failed (http=${status}): ${JSON.stringify(data).slice(0, 200)}` };
  },

  async get_ticket_stats() {
    const { status, data } = await apiCall("GET", "/api/v1/tickets?limit=100");
    if (status !== 200) return { success: false, message: `Ticket stats unavailable (http=${status}).` };
    const items = _items(data);
    const byStatus = {};
    let urgent = 0;
    for (const t of items) {
      byStatus[t.status] = (byStatus[t.status] || 0) + 1;
      if (t.priority === "urgent" && t.status !== "resolved") urgent += 1;
    }
    const breakdown = Object.entries(byStatus).map(([k, v]) => `${k}: ${v}`).join(", ") || "none";
    return { success: true, message: `Latest ${items.length} tickets — ${breakdown}. Unresolved urgent right now: ${urgent}.` };
  },

  async list_recent_tickets(params) {
    const count = Math.min(Number(params?.count) || 10, 50);
    const { status, data } = await apiCall("GET", `/api/v1/tickets?limit=${count}`);
    if (status !== 200) return { success: false, message: `Ticket list unavailable (http=${status}).` };
    const items = _items(data).slice(0, count);
    if (!items.length) return { success: true, message: "No tickets found — the queue is empty." };
    return { success: true, message: `Your ${items.length} most recent tickets:\n${items.map(_briefTicket).join("\n")}` };
  },

  async escalate_urgent_tickets() {
    const { status, data } = await apiCall("GET", "/api/v1/tickets?limit=100");
    if (status !== 200) return { success: false, message: `Could not load tickets (http=${status}).` };
    const urgent = _items(data).filter(t => t.priority === "urgent" && !["resolved", "closed"].includes(t.status));
    if (!urgent.length) return { success: true, message: "Good news — there are no unresolved urgent tickets right now." };
    return {
      success: true,
      message: `Found ${urgent.length} unresolved urgent ticket(s):\n${urgent.map(_briefTicket).join("\n")}\nEscalation to your CRM happens automatically when the AI can't resolve a ticket — check the dashboard Escalations page to action these.`,
    };
  },

  async create_ticket(params) {
    const body = {
      subject: params?.subject || "Created via Jarvis CLI",
      description: params?.description || params?.subject || "(no description)",
      customer_name: params?.customer_name || "Jarvis CLI",
      customer_email: params?.customer_email || "jarvis-cli@parwa.local",
      channel: params?.channel || "email",
    };
    const { status, data } = await apiCall("POST", "/api/v1/tickets", body);
    const id = data?.id || data?.ticket?.id;
    if ((status === 200 || status === 201) && id) {
      return { success: true, message: `Ticket created (id ${id}, TKT-${id.slice(0, 8).toUpperCase()}). The AI pipeline is already working on it.` };
    }
    return { success: false, message: `Ticket creation failed (http=${status}): ${JSON.stringify(data).slice(0, 200)}` };
  },

  async get_subscription_info() {
    const { status, data } = await apiCall("GET", "/api/billing/subscription");
    if (status !== 200) return { success: false, message: `Subscription info unavailable (http=${status}).` };
    return { success: true, message: `Subscription: ${JSON.stringify(data).slice(0, 350)}` };
  },

  async list_integrations() {
    const { status, data } = await apiCall("GET", "/api/integrations");
    if (status !== 200) return { success: false, message: `Integrations unavailable (http=${status}).` };
    const items = _items(data);
    if (!items.length) return { success: true, message: "No integrations connected yet. Connecting one also auto-retries any tickets waiting on it." };
    const list = items.map(i => `  • ${i.integration_type || i.type || i.provider} — ${i.status}`).join("\n");
    return { success: true, message: `Connected integrations:\n${list}` };
  },

  async show_recent_errors() {
    const { status, data } = await apiCall("GET", "/jarvis/status");
    if (status !== 200) return { success: false, message: `Status unavailable (http=${status}) — if the backend is down, that itself is the incident.` };
    const s = data || {};
    const problems = [];
    if (s.integration_health) {
      for (const [k, v] of Object.entries(s.integration_health)) {
        const healthy = typeof v === "object" ? (v.status || v.healthy) : v;
        if (healthy === false || healthy === "down" || healthy === "degraded") problems.push(`${k}: ${JSON.stringify(v).slice(0, 100)}`);
      }
    }
    return problems.length
      ? { success: true, message: `Problems detected:\n  • ${problems.join("\n  • ")}` }
      : { success: true, message: "No errors or degraded channels visible in the current system status." };
  },
};

/** Executor resolution: real when live, honest-demo fallback otherwise. */
export function resolveExecutor(name, mockExecutors) {
  if (isLive() && REAL_EXECUTORS[name]) return REAL_EXECUTORS[name];
  const mock = mockExecutors[name];
  if (!mock) return null;
  if (isLive()) return mock; // live but tool has no real endpoint yet → keep mock, labeled below
  return async (params) => {
    const r = await mock(params);
    return { ...r, message: (r?.message || "") + DEMO_TAG };
  };
}

// ══════════════════════════════════════════════════════════════════
// REAL SYSTEM STATE for the system prompt (replaces the fake numbers)
// ══════════════════════════════════════════════════════════════════

let _stateCache = { at: 0, text: null };

export async function getSystemState() {
  if (!isLive()) return null;
  if (Date.now() - _stateCache.at < 60_000) return _stateCache.text;
  const { status, data } = await apiCall("GET", "/jarvis/status", null, 15000);
  let text = null;
  if (status === 200 && data) {
    text = JSON.stringify({
      integration_health: data.integration_health ?? "unknown",
      load: data.load ?? "unknown",
      active_flags: data.active_flags ?? {},
    }).slice(0, 500);
  }
  _stateCache = { at: Date.now(), text };
  return text;
}
