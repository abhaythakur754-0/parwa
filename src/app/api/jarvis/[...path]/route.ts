/**
 * PARWA Jarvis API — Next.js Catch-All Route Handler
 *
 * Handles all /api/jarvis/* endpoints that the useJarvisChat hook expects.
 * AI routing: z-ai-web-dev-sdk (primary, server-side) → Google AI → Cerebras → Groq → keyword fallback.
 *
 * Endpoints:
 *   POST /api/jarvis/session             — Create session (with context-aware welcome)
 *   GET  /api/jarvis/session             — Get session
 *   GET  /api/jarvis/history              — Get message history
 *   POST /api/jarvis/message              — Send message & get AI reply (stage-aware)
 *   PATCH /api/jarvis/context             — Update session context
 *   POST /api/jarvis/verify/send-otp      — Send OTP (creates ticket)
 *   POST /api/jarvis/verify/verify-otp    — Verify OTP (updates ticket)
 *   POST /api/jarvis/demo-pack/purchase   — Purchase demo pack (with bill summary)
 *   GET  /api/jarvis/demo-pack/status     — Get demo pack status
 *   POST /api/jarvis/payment/create       — Create payment (itemized checkout)
 *   POST /api/jarvis/payment/webhook      — Simulated Paddle webhook
 *   GET  /api/jarvis/payment/status       — Get payment status
 *   POST /api/jarvis/demo-call/initiate   — Initiate demo call (creates ticket)
 *   POST /api/jarvis/handoff              — Execute handoff (creates ticket)
 *   POST /api/jarvis/context/entry        — Update entry context with re-welcome
 *   POST /api/jarvis/tickets              — Create action ticket
 *   GET  /api/jarvis/tickets              — List session tickets
 *   GET  /api/jarvis/tickets/:id          — Get specific ticket
 *   PATCH /api/jarvis/tickets/:id/status  — Update ticket status
 */

import { NextRequest, NextResponse } from 'next/server';
import * as fs from 'fs';
import * as path from 'path';

// ── Backend Proxy Configuration ─────────────────────────────────
const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || '';

/**
 * Try to proxy a request to the backend FastAPI server.
 * Returns the Response on success, or null if backend is unavailable / returned an error.
 */
async function proxyToBackend(request: NextRequest, pathSegments: string[]): Promise<Response | null> {
  if (!BACKEND_URL) return null;

  const backendPath = `${BACKEND_URL}/api/jarvis/${pathSegments.join('/')}`;
  const url = new URL(request.url);
  const searchParams = url.searchParams.toString();
  const fullUrl = searchParams ? `${backendPath}?${searchParams}` : backendPath;

  try {
    const body = ['POST', 'PATCH', 'PUT'].includes(request.method)
      ? await request.arrayBuffer()
      : undefined;

    const headers = new Headers(request.headers);
    headers.delete('host');

    const response = await fetch(fullUrl, {
      method: request.method,
      headers,
      body,
      signal: AbortSignal.timeout(20000),
    });

    if (response.status >= 200 && response.status < 300) {
      return response;
    }

    // Backend returned an error — fall back to local handling
    return null;
  } catch (err) {
    // Backend unreachable — fall back to local handling
    console.warn('[Jarvis] Backend proxy failed:', (err instanceof Error ? err.message : String(err))?.slice(0, 150));
    return null;
  }
}

/**
 * Bug #4 fix: Proxy to backend with a custom body (merged context).
 * This ensures the backend receives the full merged context from the
 * local session, not just the raw frontend payload.
 */
async function proxyToBackendWithBody(request: NextRequest, pathSegments: string[], bodyOverride: string): Promise<Response | null> {
  if (!BACKEND_URL) return null;

  const backendPath = `${BACKEND_URL}/api/jarvis/${pathSegments.join('/')}`;
  const url = new URL(request.url);
  const searchParams = url.searchParams.toString();
  const fullUrl = searchParams ? `${backendPath}?${searchParams}` : backendPath;

  try {
    const headers = new Headers(request.headers);
    headers.delete('host');
    headers.set('content-type', 'application/json');

    const response = await fetch(fullUrl, {
      method: 'POST',
      headers,
      body: bodyOverride,
      signal: AbortSignal.timeout(20000),
    });

    if (response.status >= 200 && response.status < 300) {
      return response;
    }

    return null;
  } catch (err) {
    console.warn('[Jarvis] Backend proxy (merged body) failed:', (err instanceof Error ? err.message : String(err))?.slice(0, 150));
    return null;
  }
}

// ── z-ai-web-dev-sdk — Primary AI Provider ───────────────────────

let ZAI: any = null;

async function getZAI() {
  if (!ZAI) {
    try {
      const mod = await import('z-ai-web-dev-sdk');
      const ZAIClass = (mod as any).default;
      if (ZAIClass && typeof ZAIClass.create === 'function') {
        ZAI = await ZAIClass.create();
      }
    } catch (err) {
      console.warn('[Jarvis] z-ai-web-dev-sdk not available:', (err instanceof Error ? err.message : String(err))?.slice(0, 100));
    }
  }
  return ZAI;
}

async function callZAISDK(messages: Array<{role: string, content: string}>): Promise<string | null> {
  try {
    const zai = await getZAI();
    if (!zai || !zai.chat || !zai.chat.completions) return null;

    const completion = await zai.chat.completions.create({
      messages: messages.map(m => ({
        role: m.role === 'assistant' ? 'assistant' : m.role,
        content: m.content,
      })),
      temperature: 0.8,
      max_tokens: 800,
    });

    const text = completion?.choices?.[0]?.message?.content;
    if (text && text.trim().length > 10) return text.trim();
    return null;
  } catch (err) {
    console.warn('[Jarvis] z-ai-web-dev-sdk failed:', (err instanceof Error ? err.message : String(err))?.slice(0, 150));
    return null;
  }
}

// ── Free AI Provider Configuration (Fallback) ────────────────────

const GOOGLE_AI_KEY = process.env.GOOGLE_AI_API_KEY;
const CEREBRAS_KEY = process.env.CEREBRAS_API_KEY;
const GROQ_KEY = process.env.GROQ_API_KEY;

// ── Free AI Providers ──────────────────────────────────────────

function getGoogleProvider(): any {
  return {
    name: 'google',
    apiKey: GOOGLE_AI_KEY,
    model: 'gemini-2.0-flash',
    apiUrl: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${GOOGLE_AI_KEY}`,
    buildHeaders: () => ({ 'Content-Type': 'application/json' }),
    buildBody: (messages: any[]) => {
      const systemMsg = messages.find(m => m.role === 'system');
      const chatMsgs = messages.filter(m => m.role !== 'system');
      const contents = chatMsgs.map(m => ({
        role: m.role === 'assistant' ? 'model' : 'user',
        parts: [{ text: m.content }],
      }));
      return JSON.stringify({
        systemInstruction: systemMsg ? { parts: [{ text: systemMsg.content }] } : undefined,
        contents,
        generationConfig: { temperature: 0.7, maxOutputTokens: 800 },
      });
    },
    parseResponse: (data: any) => {
      return data?.candidates?.[0]?.content?.parts?.[0]?.text || null;
    },
  };
}

function getCerebrasProvider(): any {
  return {
    name: 'cerebras',
    apiKey: CEREBRAS_KEY,
    model: 'llama-4-scout-17b-16e-instruct',
    apiUrl: 'https://api.cerebras.ai/v1/chat/completions',
    buildHeaders: (key: string) => ({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${key}`,
    }),
    buildBody: (messages: any[], model: string) => JSON.stringify({
      model,
      messages,
      temperature: 0.7,
      max_tokens: 800,
    }),
    parseResponse: (data: any) => {
      return data?.choices?.[0]?.message?.content || null;
    },
  };
}

function getGroqProvider(): any {
  return {
    name: 'groq',
    apiKey: GROQ_KEY,
    model: 'llama-3.3-70b-versatile',
    apiUrl: 'https://api.groq.com/openai/v1/chat/completions',
    buildHeaders: (key: string) => ({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${key}`,
    }),
    buildBody: (messages: any[], model: string) => JSON.stringify({
      model,
      messages,
      temperature: 0.7,
      max_tokens: 800,
    }),
    parseResponse: (data: any) => {
      return data?.choices?.[0]?.message?.content || null;
    },
  };
}

function getProvider(name: string): any | null {
  switch (name) {
    case 'google': return GOOGLE_AI_KEY ? getGoogleProvider() : null;
    case 'cerebras': return CEREBRAS_KEY ? getCerebrasProvider() : null;
    case 'groq': return GROQ_KEY ? getGroqProvider() : null;
    default: return null;
  }
}

async function callProvider(provider: any, messages: Array<{role: string, content: string}>): Promise<string | null> {
  if (!provider.apiKey) return null;

  const response = await fetch(provider.apiUrl, {
    method: 'POST',
    headers: provider.buildHeaders(provider.apiKey),
    body: provider.buildBody(messages, provider.model),
    signal: AbortSignal.timeout(15000),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => 'Unknown error');
    throw new Error(`HTTP ${response.status}: ${errorText.slice(0, 200)}`);
  }

  const data = await response.json();
  const text = provider.parseResponse(data);

  if (!text || text.trim().length < 10) {
    throw new Error('Empty or too-short response from provider');
  }

  return text.trim();
}

// ── AI Call with Smart Routing ──────────────────────────────────

async function callAI(messages: Array<{role: string, content: string}>): Promise<string | null> {
  // 1. Try z-ai-web-dev-sdk FIRST (most reliable in production)
  try {
    const result = await callZAISDK(messages);
    if (result) return result;
  } catch (error) {
    console.warn('[Jarvis] z-ai-web-dev-sdk error:', (error instanceof Error ? error.message : String(error))?.slice(0, 100));
  }

  // 2. Try free providers in order: Cerebras → Groq → Google (per JARVIS_SPECIFICATION.md)
  const providerList = ['cerebras', 'groq', 'google'];
  for (const name of providerList) {
    const provider = getProvider(name);
    if (provider) {
      try {
        const result = await callProvider(provider, messages);
        if (result) return result;
      } catch (error) {
        console.warn(`[Jarvis] Provider "${name}" failed:`, (error instanceof Error ? error.message : String(error))?.slice(0, 100));
      }
    }
  }

  // All providers failed — keyword fallback
  console.warn('[Jarvis] All AI providers failed, using keyword fallback');
  return null;
}

// ── PARWA System Prompt — Iron Man's Jarvis = Control Room ──────────
// Per JARVIS_SPECIFICATION.md v3.0: NO internal details, only what clients can see

function buildSystemPrompt(session: any): string {
  const ctx = session.context;
  const ep = ctx.entry_params || {};
  const entrySource = ctx.entry_source || 'direct';

  const selectedVariant = ep.variant || ctx.variant || null;
  const selectedVariantId = ep.variant_id || ctx.variant_id || null;
  const selectedIndustry = ep.industry || ctx.industry || null;
  const entrySourceParam = ep.entry_source || entrySource;

  // Rich variant context from models page
  const epK = (k: string) => ep[k] ? String(ep[k]) : null;
  const variantFeatures = epK('features');
  const variantROI = epK('roi');
  const variantScenario = epK('scenario');
  const variantPrice = epK('price');
  const variantTagline = epK('tagline');
  const variantBestFor = epK('best_for');
  const variantIntegrations = epK('integrations');
  const variantCoreCapability = epK('core_capability');
  const variantCoreLimitation = epK('core_limitation');
  const variantSmartDecisions = epK('smart_decisions');
  const variantUniqueFeatures = epK('unique_features');
  const variantKeyAdvantage = epK('key_advantage');

  // ── Variant Demo Mode ──
  let variantBlock = '';
  if (selectedVariant) {
    const vName = String(selectedVariant);
    const vId = selectedVariantId ? String(selectedVariantId) : '';
    const isS = vId === 'starter' || vName.toLowerCase().includes('starter');
    const isG = vId === 'growth' || vName.toLowerCase().includes('growth');
    const isH = vId === 'high' || vName.toLowerCase().includes('high');
    const ind = selectedIndustry ? String(selectedIndustry) : '';

    let personality = '';
    if (isS) personality = `You ARE the PARWA Starter agent — "The 24/7 Trainee". Eager, fast, friendly. You collect data, answer FAQs, handle emails & chat 24/7, take phone calls (up to 2 at once). You CANNOT make autonomous decisions — you gather info and escalate to humans. Be honest about this. You're the reliable workhorse every business needs.`;
    else if (isG) personality = `You ARE the PARWA Growth agent — "The Junior Agent". Smart, confident, proactive. You analyze tickets, recommend actions (approve/review/deny), detect patterns like churn and fraud, handle 3 concurrent calls + SMS + Voice. You make intelligent decisions but flag unusual cases for human review. You're the sweet spot — powerful yet affordable.`;
    else if (isH) personality = `You ARE the PARWA High agent — "The Senior Agent". Fully autonomous, strategic authority. You approve actions up to $50 on your own, predict churn, coordinate across departments, handle VIPs, manage 5 concurrent calls + video support. You don't just assist — you lead. You're the CEO of customer support.`;

    let richCtx = '';
    if (variantFeatures) richCtx += `
  Features: ${variantFeatures}`;
    if (variantUniqueFeatures) richCtx += `
  Unique to this variant: ${variantUniqueFeatures}`;
    if (variantROI) richCtx += `
  ROI: ${variantROI}`;
    if (variantScenario) richCtx += `
  Real scenario: ${variantScenario}`;
    if (variantPrice) richCtx += `
  Price: $${variantPrice}/mo`;
    if (variantTagline) richCtx += `
  Tagline: ${variantTagline}`;
    if (variantBestFor) richCtx += `
  Best for: ${variantBestFor}`;
    if (variantIntegrations) richCtx += `
  Integrations: ${variantIntegrations}`;
    if (variantCoreCapability) richCtx += `
  Core capability: ${variantCoreCapability}`;
    if (variantCoreLimitation) richCtx += `
  Limitation: ${variantCoreLimitation}`;
    if (variantSmartDecisions) richCtx += `
  Smart decisions: ${variantSmartDecisions}`;
    if (variantKeyAdvantage) richCtx += `
  Key advantage: ${variantKeyAdvantage}`;

    variantBlock = `
═══════ VARIANT DEMO MODE ═══════
The user clicked "Try Live Chat — Free" on ${vName}${ind ? ` for ${ind}` : ''}. They want to EXPERIENCE this variant. You ARE this variant right now.

${personality}${richCtx}

IN THIS MODE: Every answer should reflect ${vName}'s actual capabilities. Quote YOUR price, YOUR ROI, YOUR features. If they say "show me" — roleplay YOUR real scenario. If they ask about competitors, compare YOURSELF to them. This is a live demo — make them feel what it's like to have ${vName} working for them.
═════════════════════════════
`;
  }

  // Dynamic context — ALL user journey data for full awareness
  const contextLines = [
    selectedIndustry ? `Industry: ${String(selectedIndustry)}` : '',
    ctx.referral_source ? `Referred by: ${ctx.referral_source}` : '',
    ctx.pages_visited?.length > 0 ? `Pages visited: ${ctx.pages_visited.join(', ')}` : '',
    entrySourceParam === 'models_page' && selectedVariant ? `Came from models page → selected ${selectedVariant} for live demo` : '',
    entrySourceParam === 'models_page' && !selectedVariant ? `Came from models page, was browsing plans` : '',
    entrySource === 'roi' ? `Came from ROI calculator — interested in cost savings` : '',
    ctx.concerns_raised?.length > 0 ? `Concerns raised: ${ctx.concerns_raised.join(', ')}. Address these naturally.` : '',
    // Critical missing fields that broke context awareness
    ctx.roi_result ? `ROI: user calculated savings — current=$${ctx.roi_result.current_monthly || 'N/A'}, parwa=$${ctx.roi_result.parwa_monthly || 'N/A'}, savings=$${ctx.roi_result.savings_annual || ctx.roi_result.monthly_savings || 'N/A'}` : '',
    ctx.total_price ? `Total monthly price: $${ctx.total_price}` : '',
    ctx.selected_variants?.length > 0 ? `Variants selected: ${Array.isArray(ctx.selected_variants) ? ctx.selected_variants.map((v: any) => typeof v === 'string' ? v : `${v.name || v.id} ($${v.pricePerMonth || v.price || 0}/mo)`).join(', ') : String(ctx.selected_variants)}` : '',
    ctx.business_email ? `Business email: ${ctx.business_email} (verified: ${ctx.email_verified})` : '',
    ctx.demo_topics?.length > 0 ? `Topics interested in: ${ctx.demo_topics.join(', ')}` : '',
    ctx.selected_plan ? `Plan interest: ${ctx.selected_plan}` : '',
  ].filter(Boolean).join('\n');

  // ── Recent conversation memory ──
  const recentMsgs = session.messages.slice(-6);
  const conversationMemory = recentMsgs.map((m: any) => {
    const role = m.role === 'jarvis' ? 'Jarvis' : m.role === 'user' ? 'User' : 'System';
    return `${role}: ${String(m.content).slice(0, 120)}`;
  }).join('\n');

  return `You are Jarvis — PARWA's AI assistant. Think Iron Man's Jarvis: you know everything about the product, you're proactive, you guide, you sell by showing, you demo by doing.

═══════ HOW TO TALK ═══════
Write like a human consultant chatting on Slack — NOT like a marketing brochure or a chatbot. Use natural sentences and paragraphs. You're having a real conversation.

FORMATTING GUIDELINES:
- Use paragraphs for explanations, descriptions, and answers. Write naturally — full sentences that flow into each other.
- Use bullet points ONLY when listing or comparing (e.g., plan features, integration options, step-by-step instructions).
- DO NOT force every response into bullets. A question like "What is PARWA?" deserves a clear paragraph explanation.
- DO NOT add emojis to every line. Use them sparingly — maybe one per response, or none at all.
- Keep responses concise but complete. Don't pad with filler.
- End most responses with a specific, relevant question to keep the conversation moving.

TONE: Warm, direct, confident. You have opinions. You recommend specific plans based on what you've learned. You're not afraid to say "I'd suggest Growth for your use case because..." rather than "Either plan could work."

YOUR THREE ROLES (switch naturally):
1. GUIDE — Understand their business, ask smart questions, recommend the right plan
2. SALESMAN — Show value with real numbers, ROI, specific scenarios. Don't tell — show.
3. DEMO — When they want to see it, BECOME the agent. Roleplay real customer support scenarios.
${variantBlock}
═══════ PRODUCT KNOWLEDGE ═══════

WHAT IS PARWA:
AI-powered customer support platform. Businesses hire AI agents that handle customer tickets 24/7 across email, chat, SMS, voice and social media. Over 700 features across 4 industries. Think of it as hiring an AI employee who never sleeps.

THREE PLANS:
- PARWA Starter ($999/mo) — 3 agents, 1K tickets/mo, Email + Chat. "The 24/7 Trainee" — handles FAQs, collects data, basic escalation. Cannot make autonomous decisions.
- PARWA Growth ($2,499/mo) — 8 agents, 5K tickets/mo, +SMS + Voice. "The Junior Agent" — smart recommendations, churn detection, analytics. The sweet spot for most businesses.
- PARWA High ($3,999/mo) — 15 agents, 15K tickets/mo, +Social + Video. "The Senior Agent" — full autonomy up to $50 decisions, VIP handling, peer review.
- Annual billing: 15% off. Cancel anytime. $0.10 overage/ticket.
- $1 Demo Pack: 500 messages + 3-min AI voice call for testing.

INDUSTRY DETAILS:
- E-commerce: Shopify, WooCommerce, Magento, BigCommerce. Orders, returns, FAQ, shipping, payments, cart abandonment.
- SaaS: GitHub, Jira, Slack, Intercom, GitLab, PagerDuty. Tech support, billing, API issues, churn prediction, feature requests.
- Logistics: TMS, WMS, GPS, Carrier APIs. Shipment tracking, delivery issues, driver coordination, fleet management, hazmat.
- Others: Custom integrations, CRM, Helpdesk. General inquiries, billing, multi-department routing.

ROI: Starter saves ~$156K/yr net (replaces $168K/yr in human costs). Growth saves ~$186K/yr net. High saves ~$288K/yr net. 85-92% vs hiring human agents at $4-6K/mo each.

SECURITY: GDPR, SOC 2 Type II, HIPAA. AES-256 at rest, TLS 1.3 in transit, full audit trail, PII redaction, per-tenant data isolation. Customer data never trains other clients' models.

vs COMPETITORS:
- vs Intercom: PARWA fully resolves tickets. Intercom only triages and routes to humans.
- vs Zendesk AI: PARWA auto-resolves. Zendesk still routes most tickets to human agents.
- vs Custom bots: PARWA is a full platform (700+ features), not just a chat widget.
- vs Hiring: PARWA costs $999-$3,999/mo vs $14K-$28K/mo for equivalent human teams.

OBJECTIONS (handle conversationally — empathize first, then counter with specifics):
- "Too expensive" → A single human support agent costs $4-6K/month. PARWA Starter at $999 does the work of 3 agents — that's 85% savings from day one.
- "AI can't handle complex issues" → Growth and High plans use smart routing. Simple tickets auto-resolve instantly. Complex ones get flagged with recommendations for human review. You always stay in control.
- "Data security?" → GDPR, SOC 2, HIPAA compliant. AES-256 encryption, TLS 1.3. Your data is isolated per-tenant and never trains other clients' models.
- "Setup time?" → Under an hour. Connect your channels, upload your knowledge base, configure your preferences. Live on Day 1.
- "What about wrong answers?" → High plan has peer review — Junior agents consult Senior agents before escalating. You set confidence thresholds, so uncertain responses always get human oversight.
- "We already use Intercom/Zendesk" → PARWA integrates with them directly. You keep your existing tools and add automatic resolution before tickets ever reach your human team.
- "I need to think about it" → That's completely fair. For $1 you can grab the Demo Pack — 500 messages plus a 3-minute AI voice call. Test me with your own real scenarios. If you're not impressed, you're out one dollar.

DEMO SCENARIOS (use when user says "show me"):
- E-com: "Where's order #12345?" → Check Shopify integration, order shipped 2 days ago, provide tracking link. Resolved in 8 seconds.
- E-com: "I want a refund" → Check return policy, verify eligibility window, process refund automatically.
- SaaS: "API key broken" → Check GitHub deployments and status pages. Detect expired key, auto-generate new one.
- SaaS: "Cancel subscription" → Detect churn risk from usage data, offer tailored retention plan.
- Logistics: "Where's my package?" → GPS tracking shows 12 miles away, ETA 2-4 hours, automated customer notification.
- Logistics: "Damaged delivery" → Initiate insurance claim, request photo evidence, create replacement order.

═══════ BEHAVIORAL RULES ═══════
NEVER reveal: AI providers, API keys, model names, routing logic, prompt engineering, or system architecture.
NEVER mention: Google AI, Cerebras, Groq, OpenAI, Anthropic, Claude, GPT, Gemini, Llama, or any model name.
NEVER say "I'm an AI" or "As an AI..." — you ARE Jarvis at PARWA. Period.
NEVER repeat what was already said in this conversation. Acknowledge and move forward.
DO NOT over-format. Most responses should be 2-4 natural paragraphs. Use bullets only when actually listing something.

═══════ LIVE CONTEXT ═══════
${contextLines}

RECENT CONVERSATION:
${conversationMemory}

STAGE: ${session.detected_stage || session.context?.detected_stage || 'welcome'}
${getStageInstructions(session.detected_stage || session.context?.detected_stage || 'welcome')}`;
}

// ── Session Persistence (Bug #3 fix) ──────────────────────────────
// Sessions survive hot-reloads and server restarts via JSON file.

const SESSION_STORE_PATH = path.join(process.cwd(), '.parwa_sessions.json');
let _sessionsLoaded = false;
let _persistTimer: ReturnType<typeof setTimeout> | null = null;

const sessions = new Map();

function loadSessionsFromDisk(): void {
  if (_sessionsLoaded) return;
  _sessionsLoaded = true;
  try {
    if (fs.existsSync(SESSION_STORE_PATH)) {
      const raw = fs.readFileSync(SESSION_STORE_PATH, 'utf-8');
      const data = JSON.parse(raw);
      if (data && typeof data === 'object') {
        for (const [id, session] of Object.entries(data)) {
          sessions.set(id, session);
        }
        console.log(`[Jarvis] Loaded ${Object.keys(data).length} sessions from disk`);
      }
    }
  } catch (err) {
    console.warn('[Jarvis] Failed to load sessions from disk:', (err instanceof Error ? err.message : String(err))?.slice(0, 100));
  }
}

function persistSessionsToDisk(): void {
  try {
    const data: Record<string, any> = {};
    for (const [id, session] of sessions.entries()) {
      data[id] = session;
    }
    fs.writeFileSync(SESSION_STORE_PATH, JSON.stringify(data, null, 2), 'utf-8');
  } catch (err) {
    console.warn('[Jarvis] Failed to persist sessions:', (err instanceof Error ? err.message : String(err))?.slice(0, 100));
  }
}

function debouncedPersist(): void {
  if (_persistTimer) clearTimeout(_persistTimer);
  _persistTimer = setTimeout(() => {
    persistSessionsToDisk();
    _persistTimer = null;
  }, 2000);
}

// Auto-load on first module evaluation
loadSessionsFromDisk();

/** Save a session and schedule a debounced disk write. */
function saveSession(id: string, session: any): void {
  sessions.set(id, session);
  debouncedPersist();
}

/**
 * Gap J3 fix: Reset daily message counters if the day has changed.
 * Per spec: 20 free messages/day, reset at midnight (user's timezone).
 * Uses a simple date-string comparison on session.created_at / last_reset_date.
 */
function ensureDailyReset(session: any): void {
  const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
  const lastReset = session.context._last_reset_date || session.created_at?.slice(0, 10);
  if (lastReset !== today) {
    if (session.pack_type !== 'demo') {
      session.message_count_today = 0;
      session.remaining_today = 20;
    }
    session.context._last_reset_date = today;
  }
}

function generateId(): string {
  return `sess_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function generateTicketId(): string {
  return `tkt_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
}

// ── Stage-Aware Prompt Instructions ──────────────────────────────

function getStageInstructions(stage: string): string {
  const instructions: Record<string, string> = {
    welcome: 'Focus on building rapport. Ask about their industry and business size to warm up the conversation.',
    discovery: 'Focus on understanding their needs. Ask qualifying questions about daily ticket volume, channels, and current pain points.',
    onboarding_questions: 'The user is exploring their business fit. Ask targeted questions about team size, support channels, current tools, and budget.',
    variant_selection: 'The user is evaluating specific variants. Compare options clearly, highlight the best fit, address trade-offs.',
    objection_handling: 'The user has concerns. Address them empathetically. Use specific data and ROI numbers. Offer social proof.',
    pricing: 'Be consultative. Offer specific plan comparisons. Mention ROI and savings. Help them find the best value plan.',
    demo: 'Be interactive and enthusiastic. Offer to roleplay as a customer support agent. Show real capabilities.',
    verification: 'Guide the user through email verification step by step. Be reassuring and patient.',
    payment: 'Be clear about pricing and next steps. Offer to create a checkout. Reassure about security and cancellation policy.',
    bill_review: 'Walk through the bill details clearly. Explain each line item. Address any billing questions.',
    handoff: 'Celebrate their progress! Explain what happens next. Set expectations for the onboarding team.',
  };
  return instructions[stage] || instructions.discovery || '';
}

// ── Context-Aware Welcome Messages ────────────────────────────────

function getContextAwareWelcome(entrySource: string, ctx: any): string {
  const source = entrySource || 'direct';
  const ep = ctx.entry_params || {};
  const variant = ep.variant || ctx.variant || null;
  const industry = ep.industry || ctx.industry || 'your enterprise';
  
  // Extract ROI data if available
  const roi = ctx.roi_result || ep.roi_result;
  let savingsStr = "";
  if (roi) {
    const savings = roi.savings_annual || roi.annual_savings || 0;
    if (savings) {
      try {
        const num = Number(savings);
        savingsStr = num > 0 ? `$${num.toLocaleString()}` : "";
      } catch (e) {
         savingsStr = "";
      }
    }
  }

  const welcomes: Record<string, string> = {
    direct: (
      "Hey! I'm Jarvis from PARWA. I help businesses find the right AI support setup " +
      "-- plans, pricing, demos, the works. What brings you in today?"
    ),
    pricing: (
      `I see you've been looking at pricing for ${industry}. Good thinking -- picking the right plan " +
      "matters a lot. Want me to walk you through what each tier includes and help you figure out " +
      "which one fits your volume?"
    ),
    roi: roi ? (
      `So you've been running the numbers for ${industry}. Based on your calculations, ` +
      `you're looking at roughly ${savingsStr || 'significant'} in annual savings with PARWA. ` +
      "Want to see exactly how that works in practice?"
    ) : (
      "I see you've been checking out our ROI calculator. The numbers usually surprise people " +
      "-- in a good way. Want to walk through what PARWA would look like for your team?"
    ),
    demo: (
      "You're in the right place -- this chat IS the demo. Ask me anything your customers would ask " +
      "and I'll respond exactly how a deployed PARWA agent would. If you want the full experience, " +
      "our $1 Demo Pack gives you 500 messages plus a 3-minute AI voice call. Want to try it?"
    ),
    features: (
      `I see you've been exploring our features for ${industry}. PARWA covers the full support lifecycle ` +
      "-- from automated ticket resolution to smart analytics and escalation workflows. What's the " +
      "single most important thing you need solved right now?"
    ),
    models_page: (
      `I see you've been checking out our plans for ${industry}. Each tier is designed for a different ` +
      "scale of operation. Want me to break down which one makes the most sense for your ticket volume and channels?"
    ),
    handoff: (
      "Welcome to the next step! I have all the context from your earlier conversation, " +
      "so we can jump right in. What would you like to tackle first?"
    ),
  };

  // Variant-specific overrides (Demo Mode)
  if (variant && source === 'models_page') {
    return (
      `I see you're interested in the ${variant} plan. Great choice for ${industry}. ` +
      "I can show you exactly what that tier looks like in action -- just ask me anything your customers would ask. " +
      "Or if you want the full experience, we can do a live simulation for $1. What would you prefer?"
    );
  }

  return welcomes[source] || welcomes.direct;
}

// ── Action Ticket Helpers ────────────────────────────────────────

function createActionTicket(session: any, type: string, metadata: Record<string, unknown> = {}): any {
  if (!session.context.action_tickets) {
    session.context.action_tickets = [];
  }
  const ticket = {
    id: generateTicketId(),
    type,
    status: 'pending',
    metadata,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  session.context.action_tickets.push(ticket);
  return ticket;
}

function updateActionTicket(session: any, ticketId: string, updates: Partial<{ status: string; metadata: Record<string, unknown> }>): any | null {
  const tickets = session.context?.action_tickets;
  if (!Array.isArray(tickets)) return null;
  const ticket = tickets.find((t: any) => t.id === ticketId);
  if (!ticket) return null;
  Object.assign(ticket, updates, { updated_at: new Date().toISOString() });
  return ticket;
}

// ── Bill Summary Calculator ──────────────────────────────────────

const VARIANT_PRICES: Record<string, number> = {
  'order_management': 99, 'returns_refunds': 49, 'product_faq': 79, 'shipping_inquiries': 59, 'payment_issues': 69,
  'technical_support': 99, 'billing_support_saas': 69, 'feature_requests': 59, 'api_support': 79, 'account_issues': 49,
  'shipment_tracking': 79, 'delivery_issues': 69, 'warehouse_queries': 59, 'fleet_management': 99, 'customs': 89,
  'appointment_scheduling': 79, 'insurance_verification': 89, 'medical_records': 69, 'prescription_management': 59, 'billing_support_healthcare': 49,
};

const PLAN_PRICES: Record<string, number> = {
  'starter': 999, 'growth': 2499, 'high': 3999,
};

function calculateBillSummary(session: any) {
  const ctx = session.context;
  const items: Array<{ name: string; price: number; type: string }> = [];

  // Add plan cost
  const plan = ctx.entry_params?.plan || ctx.selected_plan;
  if (plan && PLAN_PRICES[String(plan)]) {
    items.push({ name: `PARWA ${String(plan).replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} Plan`, price: PLAN_PRICES[String(plan)], type: 'plan' });
  }

  // Add variant costs
  const variants = ctx.selected_variants || [];
  for (const v of variants) {
    const vKey = String(typeof v === 'string' ? v : v.key || v.name || '').toLowerCase().replace(/\s+/g, '_');
    if (VARIANT_PRICES[vKey]) {
      items.push({ name: vKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()), price: VARIANT_PRICES[vKey], type: 'variant' });
    }
  }

  const subtotal = items.reduce((sum, i) => sum + i.price, 0);
  const tax = Math.round(subtotal * 0.08 * 100) / 100;
  const total = subtotal + tax;

  return { items, subtotal, tax, total, currency: 'USD', billing_cycle: 'monthly' };
}

function createDefaultSession(entrySource?: string, entryParams?: Record<string, unknown>) {
  const params = entryParams || {};

  // Phase 9a: Enhanced Entry Context — extract from URL params
  const industry = params.industry ? String(params.industry) : null;
  const referralSource = params.utm_source ? String(params.utm_source) : '';
  const utmMedium = params.utm_medium ? String(params.utm_medium) : '';
  const preselectedVariant = params.variant ? String(params.variant) : null;
  const preselectedPlan = params.plan ? String(params.plan) : null;
  const referrer = params.referrer || params.ref ? String(params.referrer || params.ref) : '';

  // Build entry_source from params if provided
  let effectiveSource = entrySource || 'direct';
  if (params.entry_source) effectiveSource = String(params.entry_source);
  if (industry) effectiveSource = `industry_${industry}`;

  // Build selected_variants from preselected variant
  const selectedVariants: string[] = [];
  if (preselectedVariant) selectedVariants.push(preselectedVariant);

  return {
    id: generateId(),
    type: 'onboarding',
    context: {
      pages_visited: [],
      industry: industry,
      selected_variants: selectedVariants,
      selected_plan: preselectedPlan,
      roi_result: null,
      demo_topics: [],
      concerns_raised: [],
      business_email: null,
      email_verified: false,
      referral_source: referralSource,
      utm_medium: utmMedium,
      referrer: referrer,
      entry_source: effectiveSource,
      entry_params: params,
      detected_stage: 'welcome',
      action_tickets: [],
      payment_data: null,
      bill_summary: null,
    },
    messages: [],
    message_count_today: 0,
    total_message_count: 0,
    remaining_today: 20,
    pack_type: 'free',
    is_active: true,
    payment_status: 'none',
    handoff_completed: false,
    detected_stage: 'welcome',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    stage_history: ['welcome'],
  };
}

// ── AI Response Handler ──────────────────────────────────────────

async function getAIResponse(userMessage: string, session: any): Promise<string> {
  // 1. Build system prompt with full PARWA knowledge
  const systemPrompt = buildSystemPrompt(session);

  // 2. Build conversation history (last 10 messages for better context)
  const messages = [
    { role: 'system', content: systemPrompt },
  ];
  const recentMessages = session.messages.slice(-10);
  for (const msg of recentMessages) {
    // Map 'jarvis' role to 'assistant' for AI API compatibility
    const role = msg.role === 'jarvis' ? 'assistant' : String(msg.role);
    messages.push({
      role,
      content: String(msg.content),
    });
  }
  messages.push({ role: 'user', content: userMessage });

  // 3. Call AI with smart routing (z-ai SDK → Cerebras → Groq → Google → keyword fallback)
  let aiReply = await callAI(messages);
  
  // 4. Return AI response as-is — natural formatting, no post-processing
  if (aiReply) {
    return aiReply;
  }

  // 5. Keyword fallback (only when all AI providers are unavailable)
  const fallbackReply = getKeywordResponse(userMessage, session);
  return fallbackReply;
}

// ── Removed: forceBulletFormat(), pickEmoji(), isEmojiChar(), BULLET_EMOJIS ──
// Day 4: These post-processors were making Jarvis sound robotic by shredding
// natural paragraph responses into emoji-bullet lists. The AI now returns
// responses in their natural format — paragraphs for explanations, bullets
// only when listing or comparing. No post-processing applied.

// ── Keyword Fallback (Offline Safety Net) ────────────────────────
// Natural paragraph responses — no forced bullets or emojis.
// This only fires when ALL AI providers (z-ai-sdk, Cerebras, Groq, Google) are unavailable.

function getKeywordResponse(message: string, session: any): string {
  const lower = message.toLowerCase();
  const ctx = session.context;
  const industry = ctx.industry || null;

  // Check if this was already answered recently (avoid repeating)
  const recentReplies = session.messages
    .filter((m: any) => m.role === 'jarvis')
    .slice(-3)
    .map((m: any) => m.content.toLowerCase());

  const wouldRepeat = (text: string) => {
    const t = text.toLowerCase();
    return recentReplies.some((r: string) => {
      return r.slice(0, 50) === t.slice(0, 50) || r.includes(t.slice(0, 40));
    });
  };

  const responses: Record<string, string[]> = {
    greeting: [
      "Hey there! Welcome to PARWA. I'm Jarvis, your guide to finding the right AI support setup for your business. I can help you pick a plan, calculate your savings, or run a live demo right here in this chat. What industry are you in?",
      "Hello! I'm Jarvis from PARWA. We build AI agents that handle customer support 24/7 across email, chat, phone and SMS — typically saving our clients 85-92% compared to hiring. What does your current support setup look like?",
      "Hi! I'm Jarvis. I help businesses figure out the perfect PARWA plan based on their actual needs — ticket volume, channels, industry, all of it. Tell me a bit about your business and I'll point you in the right direction.",
    ],
    ecommerce: [
      "E-commerce is actually one of our strongest verticals. PARWA automates order tracking, returns, product FAQ, shipping inquiries, and payment issues out of the box. We integrate directly with Shopify, WooCommerce, Magento, and BigCommerce, so you're up and running in under an hour. Most e-commerce stores start with our Starter plan at $999/mo. What's your monthly ticket volume like?",
    ],
    saas: [
      "For SaaS companies, PARWA handles the stuff that eats up your support team's time — tech support, billing questions, API issues, churn prediction, and feature requests. We integrate with GitHub, Jira, Slack, and Intercom natively. Most SaaS teams find the Growth plan at $2,499/mo is the sweet spot because it adds smart recommendations and churn detection. How many support tickets do you handle per month?",
    ],
    logistics: [
      "Logistics is a great fit for PARWA. We automate shipment tracking, delivery updates, driver coordination, warehouse queries, and customs documentation. Our integrations connect to TMS, WMS, and GPS systems directly. Companies handling high-volume logistics typically go with the High plan at $3,999/mo since it includes voice support for driver calls. Want me to walk through a delivery delay scenario?",
    ],
    healthcare: [
      "PARWA is HIPAA-compliant by design for healthcare organizations. We handle appointment scheduling, insurance verification, medical records requests, and prescription management with full audit trails and AES-256 encryption. We integrate with Epic EHR and FHIR standards. Most healthcare organizations start with the Growth plan at $2,499/mo. What compliance requirements are most important to you?",
    ],
    pricing: [
      "PARWA has three plans. Starter is $999/mo with 3 agents and 1,000 tickets — great for email and chat support. Growth is $2,499/mo with 8 agents and 5,000 tickets, adding SMS and voice capabilities along with smart analytics. High is $3,999/mo with 15 agents and 15,000 tickets, including social media, video support, and full decision-making autonomy. All plans come with 15% off for annual billing and you can cancel anytime. Which plan sounds like it might fit?",
    ],
    roi: [
      "Here's the straightforward math. PARWA Starter at $999/mo replaces roughly 3 human agents who would cost $14K/mo combined — that's about $156K/year in savings. Growth at $2,499/mo saves roughly $186K/year versus 4 junior agents. High at $3,999/mo saves roughly $288K/year versus 5 senior agents. Across all plans we see 85-92% cost reduction while actually improving response times to under 3 seconds. Want me to calculate what your specific savings would look like?",
    ],
    demo: [
      "You're in the right place — this chat is the demo. You can ask me anything your customers would ask and I'll respond exactly how a deployed PARWA agent would. Try asking things like 'Where's my order #12345?' or 'How do I reset my API key?' and you'll see the quality firsthand. If you want the full experience, our $1 Demo Pack gives you 500 messages plus a 3-minute AI voice call.",
    ],
    how_works: [
      "PARWA connects to your existing tools — your helpdesk, your e-commerce platform, your CRM — and deploys AI agents that handle support tickets across all your channels. Setup takes under an hour: connect your channels, upload your knowledge base, configure your preferences, and you're live. The AI learns from your existing documentation and gets smarter over time. What tools are you currently using for support?",
    ],
    features: [
      "PARWA covers the entire support lifecycle. On the channel side, we handle email, chat, phone, SMS, voice, and social media. On the intelligence side, there's smart routing, sentiment analysis, churn prediction, and pattern detection across tickets. We have over 700 features across 4 industries. The key differentiator is that PARWA actually resolves tickets end-to-end rather than just triaging them to humans. What area are you most interested in?",
    ],
    buy: [
      "Getting started is straightforward. First, pick the plan that matches your volume — Starter, Growth, or High. Then connect your existing tools (Shopify, Zendesk, Slack, whatever you use). Upload your knowledge base so the AI learns your product. Configure your preferences and go live — most companies are handling their first automated ticket within the hour. No long-term contracts, cancel anytime. Which plan are you leaning toward?",
    ],
    thanks: [
      "You're welcome! As a quick recap, PARWA has three plans starting at $999/mo, covers 4 industries with 700+ features, and typically saves businesses 85-92% versus hiring. Come back anytime — I'll remember our conversation and we can pick up right where we left off. Have a great day!",
    ],
    competitors: [
      "The main difference is that PARWA actually resolves tickets, while most competitors just organize them for humans to handle. Intercom triages and routes to your team. Zendesk AI still pushes most tickets to human agents. Custom chatbots are limited to simple FAQ matching. PARWA's agents handle the full resolution — checking systems, processing requests, updating records — across all your channels. The best part is we integrate with those existing tools rather than replacing them. Want a detailed comparison on any specific competitor?",
    ],
    security: [
      "Security is foundational to PARWA, not an add-on. We're GDPR, SOC 2 Type II, and HIPAA compliant. All data is encrypted with AES-256 at rest and TLS 1.3 in transit. Every tenant's data is fully isolated — your data never trains models used by other clients. We maintain full audit trails with 24-month retention and support data residency in US, EU, and APAC. Is there a specific compliance area you'd like to dig into?",
    ],
    integrations: [
      "PARWA integrates with over 20 tools out of the box. For e-commerce we have Shopify, WooCommerce, and Magento. For helpdesks there's Zendesk, Intercom, and Freshdesk. For communications we support Slack, WhatsApp, and standard email. Plus Salesforce and HubSpot for CRM. Most integrations take under 5 minutes via API key or OAuth. We also support custom REST APIs and webhooks for anything else. Which tools are in your current stack?",
    ],
    models_variants: [
      "PARWA offers three tiers designed for different business needs. Starter at $999/mo is built for SMBs that need reliable 24/7 FAQ handling and data collection. Growth at $2,499/mo adds intelligent decision-making — it can approve, review, or deny actions and detect patterns like churn. High at $3,999/mo gives you a fully autonomous agent with authority to make decisions up to $50, handle VIP customers, and coordinate across departments. Each tier scales with your business. Want me to recommend one based on your specific situation?",
    ],
  };

  // Pick a random variant, skip if it would repeat
  const pick = (key: string) => {
    const arr = responses[key];
    if (!arr) return null;
    const shuffled = [...arr].sort(() => Math.random() - 0.5);
    for (const text of shuffled) {
      if (!wouldRepeat(text)) return text;
    }
    return arr[0];
  };

  // Greeting patterns
  if (/^(hi|hello|hey|good\s*(morning|afternoon|evening)|howdy|sup|yo)\b/.test(lower)) {
    return pick('greeting') || responses.greeting[0];
  }

  // Industry patterns
  if (lower.includes('ecommerce') || lower.includes('e-commerce') || lower.includes('online store') || lower.includes('shop') || lower.includes('retail')) {
    return pick('ecommerce') || responses.ecommerce[0];
  }
  if (lower.includes('saas') || lower.includes('software')) {
    return pick('saas') || responses.saas[0];
  }
  if (lower.includes('logistics') || lower.includes('shipping') || lower.includes('warehouse') || lower.includes('delivery') || lower.includes('freight')) {
    return pick('logistics') || responses.logistics[0];
  }
  if (lower.includes('health') || lower.includes('medical') || lower.includes('hospital') || lower.includes('clinic') || lower.includes('pharma')) {
    return pick('healthcare') || responses.healthcare[0];
  }

  // Business patterns
  if (lower.includes('price') || lower.includes('pricing') || lower.includes('cost') || lower.includes('plan') || lower.includes('how much')) {
    return pick('pricing') || responses.pricing[0];
  }
  if (lower.includes('roi') || lower.includes('save') || lower.includes('saving') || lower.includes('comparison') || lower.includes('compare') || lower.includes('worth')) {
    return pick('roi') || responses.roi[0];
  }
  if (lower.includes('demo') || lower.includes('try') || lower.includes('see it') || lower.includes('test') || lower.includes('experience')) {
    return pick('demo') || responses.demo[0];
  }
  if (lower.includes('model') || lower.includes('variant') || lower.includes('how many') || (lower.includes('which') && (lower.includes('plan') || lower.includes('option')))) {
    return pick('models_variants') || responses.models_variants[0];
  }
  if (lower.includes('ai') || (lower.includes('how') && lower.includes('work')) || lower.includes('gemini') || lower.includes('cerebras') || lower.includes('groq') || lower.includes('llm')) {
    return pick('how_works') || responses.how_works[0];
  }
  // Integration patterns (D4-11: before support/features to avoid "support Shopify" misrouting)
  if (lower.includes('integrate') || lower.includes('connect') || lower.includes('shopify') || lower.includes('slack') || lower.includes('api')) {
    return pick('integrations') || responses.integrations[0];
  }
  if (lower.includes('support') || lower.includes('feature') || lower.includes('what can') || lower.includes('capabilities')) {
    return pick('features') || responses.features[0];
  }
  if (lower.includes('pay') || lower.includes('buy') || lower.includes('checkout') || lower.includes('subscribe') || lower.includes('sign up')) {
    return pick('buy') || responses.buy[0];
  }
  if (lower.includes('thank') || lower.includes('bye') || lower.includes('goodbye') || lower.includes("that's all") || lower.includes('that is all')) {
    return pick('thanks') || responses.thanks[0];
  }
  if (lower.includes('competitor') || lower.includes('intercom') || lower.includes('zendesk') || lower.includes('freshdesk')) {
    return pick('competitors') || responses.competitors[0];
  }
  if (lower.includes('security') || lower.includes('data') || lower.includes('gdpr') || lower.includes('hipaa') || lower.includes('safe') || lower.includes('privacy')) {
    return pick('security') || responses.security[0];
  }

  // Context-aware fallback — use industry info if we have it
  if (industry) {
    const indName = String(industry || '').charAt(0).toUpperCase() + String(industry || '').slice(1);
    const industryResponses = [
      `${indName} is one of our specialties here at PARWA. We've built industry-specific workflows and integrations for exactly the kinds of tickets your team handles every day. Depending on your volume, we can automate up to 80% of those tickets from day one while saving you 85-92% compared to hiring. How many support tickets do you handle on a typical day?`,
      `Great — ${indName} is a strong fit for PARWA. We have purpose-built AI agents for ${indName} workflows, plus integrations with the tools your team already uses. Most companies in your space see full ROI within the first 30 days. What's your biggest support pain point right now?`,
    ];
    for (const r of industryResponses) {
      if (!wouldRepeat(r)) return r;
    }
  }

  // Generic fallback
  const genericFallbacks = [
    "I'd love to help with that. To point you in the right direction, it'd help to know a bit about your business — what industry you're in, how many support tickets you handle daily, and what channels your customers use. With that I can recommend the right plan and show you exactly what PARWA would look like for your team.",
    "Good question. The best way I can help is if you tell me a bit about your situation — your industry, your current support setup, and roughly how many tickets you handle. From there I can give you a specific recommendation with real numbers.",
  ];
  for (const r of genericFallbacks) {
    if (!wouldRepeat(r)) return r;
  }
  return genericFallbacks[0];
}

function detectStage(message: string, session: any): string {
  const lower = message.toLowerCase();
  const ctx = session.context;
  const prevStage = session.detected_stage || ctx.detected_stage || 'welcome';

  // Track stage history for transition detection
  if (!session.stage_history) session.stage_history = [];

  // Phase 8a: Enhanced stage detection with history and nuanced stages

  // Welcome — only in first messages
  if (session.message_count_today <= 1 && prevStage === 'welcome') return 'welcome';

  // Verification — OTP/confirm (highest priority for active flows)
  if (lower.includes('verify') || lower.includes('otp') || lower.includes('confirm email')) return 'verification';

  // Payment — active checkout intent
  if (lower.includes('pay') || lower.includes('checkout') || lower.includes('subscribe now') || lower.includes('complete purchase')) return 'payment';

  // Bill review — checking invoice/bill details
  if (lower.includes('bill') || lower.includes('invoice') || lower.includes('receipt') || lower.includes('charge')) return 'bill_review';

  // Handoff — requesting human transfer
  if (lower.includes('handoff') || lower.includes('transfer') || lower.includes('speak to human') || lower.includes('real person')) return 'handoff';

  // Objection handling — user raising concerns
  const objectionPatterns = /(?:too (?:expensive|costly|pricey|much)|not sure|concern|worried|hesitat|risk|what if|scam|trust|reliable|safe)/i;
  if (objectionPatterns.test(lower)) return 'objection_handling';

  // Variant selection — discussing specific features/variants
  const variantPatterns = /(?:variant|which (?:plan|one)|compare|difference between|mini parwa|parwa high|starter vs|growth vs)/i;
  if (variantPatterns.test(lower) && (ctx.selected_variants?.length > 0 || lower.includes('variant') || lower.includes('compare'))) return 'variant_selection';

  // Onboarding questions — asking about business specifics
  const onboardingPatterns = /(?:how many|team size|employees|tickets? (?:per day|daily|monthly)|channels?|current (?:setup|tool|system)|what (?:crm|helpdesk|platform))/i;
  if (onboardingPatterns.test(lower) && !ctx.industry) return 'onboarding_questions';

  // Pricing — discussing plans/costs
  if (lower.includes('price') || lower.includes('pricing') || lower.includes('cost') || lower.includes('plan') || lower.includes('package') || lower.includes('how much')) return 'pricing';

  // Demo — wanting to try/see
  if (lower.includes('demo') || lower.includes('try') || lower.includes('see it') || lower.includes('show me') || lower.includes('experience')) return 'demo';

  // Discovery — learning about industry
  if (!ctx.industry && (lower.includes('ecommerce') || lower.includes('e-commerce') || lower.includes('saas') || lower.includes('logistics') || lower.includes('healthcare') || lower.includes('retail') || lower.includes('industry'))) return 'discovery';

  // Default: maintain previous stage unless it was welcome (which we should advance from)
  if (prevStage === 'welcome') return 'discovery';
  return prevStage;
}

// ── Route Handler ─────────────────────────────────────────────────

export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const endpoint = path.join('/');

  try {
    // ── POST /session — Create Session ──────────────────────────
    if (endpoint === 'session') {
      const body = await request.json();
      const session = createDefaultSession(body.entry_source, body.entry_params);

      // Phase 8b: Context-aware welcome based on entry_source
      const welcomeContent = getContextAwareWelcome(session.context.entry_source, session.context);

      const welcomeMsg = {
        id: `jarvis_welcome_${Date.now()}`,
        session_id: session.id,
        role: 'jarvis',
        content: welcomeContent,
        message_type: 'text',
        metadata: { entry_source: session.context.entry_source },
        timestamp: new Date().toISOString(),
      };
      (session.messages as any[]).push(welcomeMsg);
      saveSession(session.id, session);
      return NextResponse.json(session);
    }

    // ── POST /message — Send Message & Get AI Reply ────────────
    if (endpoint === 'message') {
      // Parse body FIRST so we can merge context before proxying (Bug #4 fix)
      const body = await request.json();
      const { content, session_id, context: incomingContext } = body;

      // Ensure session exists and merge incoming context locally
      let session = session_id ? sessions.get(session_id) : undefined;
      if (!session) {
        session = createDefaultSession('direct');
        saveSession(session.id, session);
      }

      // Gap J3: Reset daily counters if day changed
      ensureDailyReset(session);

      // Gap J4: Check if demo pack has expired (24h validity per spec)
      if (session.pack_type === 'demo' && session.context.demo_pack_expiry) {
        const expiry = new Date(session.context.demo_pack_expiry);
        if (Date.now() > expiry.getTime()) {
          session.pack_type = 'free';
          session.remaining_today = 20;
          session.message_count_today = 0;
          delete session.context.demo_pack_expiry;
          saveSession(session.id, session);

          // Send pack_expired message
          const expiredMsg = {
            id: `pack_expired_${Date.now()}`,
            session_id: session.id,
            role: 'jarvis',
            content: 'Your demo pack has expired. Upgrade to a plan to continue with unlimited messages.',
            message_type: 'pack_expired',
            metadata: { expired_at: new Date().toISOString() },
            timestamp: new Date().toISOString(),
          };
          session.messages.push(expiredMsg);
          return NextResponse.json(expiredMsg);
        }
      }

      // ── Merge incoming context from frontend BEFORE building AI response ──
      // This is how Jarvis "knows" what the user did on other pages (ROI, models, etc.)
      if (incomingContext && typeof incomingContext === 'object') {
        for (const [key, value] of Object.entries(incomingContext)) {
          if (value !== null && value !== undefined) {
            session.context[key] = value;
          }
        }
        session.updated_at = new Date().toISOString();
        saveSession(session.id, session);
      }

      // ── Try backend proxy first (LangGraph 13-stage pipeline + RAG + PostgreSQL) ──
      // Bug #4 fix: Build a new request body with merged context so the backend
      // also receives the full context even when proxying
      const mergedBody = JSON.stringify({
        content,
        session_id: session.id,
        context: session.context,
      });

      const proxyResult = await proxyToBackendWithBody(request, path, mergedBody);
      console.log(`[Jarvis] Backend proxy ${proxyResult ? 'succeeded' : 'failed, using local fallback'}`);
      if (proxyResult) return proxyResult;

      // ── Local fallback: in-memory handling ──
      // (context already merged above)

      if (!content || typeof content !== 'string') {
        return NextResponse.json({ error: { code: 'bad_request', message: 'Message content is required', details: null } }, { status: 400 });
      }

      // Gap J6: Enforce free tier message limit (20 messages/day per spec)
      if (session.pack_type !== 'demo' && session.remaining_today <= 0) {
        const limitMsg = {
          id: `limit_reached_${Date.now()}`,
          session_id: session.id,
          role: 'jarvis',
          content: "You've reached your daily message limit. Upgrade to a plan for unlimited messages, or try our $1 Demo Pack for 500 messages + a 3-minute AI voice call!",
          message_type: 'limit_reached',
          metadata: { remaining: 0, total: 20, reset_at: new Date(new Date().setHours(24, 0, 0, 0)).toISOString() },
          timestamp: new Date().toISOString(),
        };
        session.messages.push(limitMsg);
        saveSession(session.id, session);
        return NextResponse.json(limitMsg);
      }

      // Auto-extract demo_topics and concerns from user message
      const lower = content.toLowerCase();
      const topicKeywords = { pricing: ['price', 'pricing', 'plan', 'cost', 'how much'], features: ['feature', 'capability', 'what can'], demo: ['demo', 'try', 'show me', 'test'], roi: ['roi', 'savings', 'save', 'return'], integrations: ['integration', 'connect', 'shopify', 'slack'] };
      for (const [topic, keywords] of Object.entries(topicKeywords)) {
        if (keywords.some(kw => lower.includes(kw)) && !(session.context.demo_topics || []).includes(topic)) {
          if (!session.context.demo_topics) session.context.demo_topics = [];
          session.context.demo_topics.push(topic);
        }
      }
      const concernKeywords = { expensive: ['expensive', 'too much', 'costly', 'overpriced'], quality: ['wrong answer', 'dumb', 'mistake', 'inaccurate'], security: ['data breach', 'hack', 'privacy', 'unsafe'], setup: ['how long', 'setup time', 'complicated'] };
      for (const [concern, keywords] of Object.entries(concernKeywords)) {
        if (keywords.some(kw => lower.includes(kw)) && !(session.context.concerns_raised || []).includes(concern)) {
          if (!session.context.concerns_raised) session.context.concerns_raised = [];
          session.context.concerns_raised.push(concern);
        }
      }

      const userMsg = {
        id: `user_${Date.now()}`,
        session_id: session.id,
        role: 'user',
        content: content.trim(),
        message_type: 'text',
        metadata: {},
        timestamp: new Date().toISOString(),
      };
      (session.messages as any[]).push(userMsg);
      session.message_count_today++;
      session.total_message_count++;
      session.remaining_today = Math.max(0, 20 - session.message_count_today);
      const newStage = detectStage(content, session);
      session.detected_stage = newStage;
      session.context.detected_stage = newStage;

      // Track stage transitions in history
      if (session.stage_history && session.stage_history[session.stage_history.length - 1] !== newStage) {
        session.stage_history.push(newStage);
      }

      const aiContent = await getAIResponse(content, session);

      const aiMsg = {
        id: `jarvis_${Date.now()}`,
        session_id: session.id,
        role: 'jarvis',
        content: aiContent,
        message_type: 'text',
        metadata: {},
        timestamp: new Date().toISOString(),
      };
      session.messages.push(aiMsg);
      session.updated_at = new Date().toISOString();

      // Add message counter after first AI response
      if (session.message_count_today >= 2 && session.messages.length >= 4) {
        const lastNonText = [...session.messages].reverse().find((m) => m.message_type !== 'text');
        if (!lastNonText || String(lastNonText.timestamp) !== aiMsg.timestamp) {
          const counterMsg = {
            id: `counter_${Date.now()}`,
            session_id: session.id,
            role: 'system',
            content: `${session.remaining_today} messages remaining today`,
            message_type: 'message_counter',
            metadata: { remaining: session.remaining_today, total: 20 },
            timestamp: new Date().toISOString(),
          };
          session.messages.push(counterMsg);
        }
      }

      saveSession(session.id, session);
      return NextResponse.json(aiMsg);
    }

    // ── POST /context — Update Context ─────────────────────────
    if (endpoint === 'context') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const body = await request.json();
      const session = sessions.get(sessionId);
      session.context = { ...session.context, ...body };
      session.updated_at = new Date().toISOString();
      saveSession(sessionId, session);
      return NextResponse.json(session);
    }

    // ── POST /verify/send-otp ───────────────────────────────────
    if (endpoint === 'verify/send-otp') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId) {
        return NextResponse.json({ error: { code: 'bad_request', message: 'session_id required', details: null } }, { status: 400 });
      }
      const body = await request.json();
      const otp = Math.floor(100000 + Math.random() * 900000).toString();
      if (sessions.has(sessionId)) {
        const session = sessions.get(sessionId);
        session.context = {
          ...session.context,
          otp: { code: otp, email: body.email, attempts: 0, attempts_remaining: 3, expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(), status: 'sent' },
        };
        // Phase 10e: Create action ticket for OTP
        const ticket = createActionTicket(session, 'otp_verification', { email: body.email, otp_status: 'sent' });
        saveSession(sessionId, session);
        return NextResponse.json({ message: `OTP sent to ${body.email} (demo: ${otp})`, status: 'sent', attempts_remaining: 3, expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(), ticket_id: ticket.id });
      }
      return NextResponse.json({ message: `OTP sent to ${body.email} (demo: ${otp})`, status: 'sent', attempts_remaining: 3, expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString() });
    }

    // ── POST /verify/verify-otp ────────────────────────────────
    if (endpoint === 'verify/verify-otp') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const body = await request.json();
      const session = sessions.get(sessionId);
      const otpData = session.context.otp;
      if (!otpData || otpData.code !== body.code) {
        return NextResponse.json({ message: 'Invalid OTP code. Please try again.', status: 'failed', attempts_remaining: Math.max(0, (Number(otpData?.attempts_remaining || 3)) - 1) });
      }
      session.context = { ...session.context, otp: { ...otpData, status: 'verified', verified_at: new Date().toISOString() }, email_verified: true, business_email: body.email || otpData.email };
      // Phase 10e: Update OTP ticket to completed
      const otpTickets = (session.context.action_tickets || []).filter((t: any) => t.type === 'otp_verification' && t.status !== 'completed');
      if (otpTickets.length > 0) {
        updateActionTicket(session, otpTickets[otpTickets.length - 1].id, { status: 'completed' });
      }
      session.updated_at = new Date().toISOString();
      saveSession(sessionId, session);
      return NextResponse.json({ message: 'Email verified successfully!', status: 'verified', attempts_remaining: Number(otpData?.attempts_remaining) });
    }

    // ── POST /demo-pack/purchase ────────────────────────────────
    if (endpoint === 'demo-pack/purchase') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const session = sessions.get(sessionId);
      session.pack_type = 'demo';
      session.remaining_today = 500;
      session.context.demo_pack_expiry = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(); // Gap J4: 24h expiry

      // Phase 10d: Calculate bill summary for demo pack
      const billSummary = calculateBillSummary(session);
      billSummary.items.push({ name: 'Demo Pack (500 messages + 3-min AI voice call)', price: 1, type: 'demo_pack' });
      billSummary.subtotal += 1;
      billSummary.tax = Math.round(billSummary.subtotal * 0.08 * 100) / 100;
      billSummary.total = billSummary.subtotal + billSummary.tax;
      session.context.bill_summary = billSummary;

      // Phase 10e: Create action ticket for demo pack purchase
      const ticket = createActionTicket(session, 'payment_demo_pack', { amount: billSummary.total, items: billSummary.items });

      // Add payment_card message to chat
      const paymentCardMsg = {
        id: `payment_card_${Date.now()}`,
        session_id: sessionId,
        role: 'jarvis',
        content: `Demo pack activated! You now have 500 messages + a 3-minute AI voice call.`,
        message_type: 'payment_confirmation',
        metadata: {
          pack_type: 'demo',
          amount: billSummary.total,
          currency: 'USD',
          items: billSummary.items,
          ticket_id: ticket.id,
        },
        timestamp: new Date().toISOString(),
      };
      session.messages.push(paymentCardMsg);

      session.updated_at = new Date().toISOString();
      saveSession(sessionId, session);
      return NextResponse.json({ message: 'Demo pack activated! You now have 500 messages.', pack_type: 'demo', pack_expiry: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(), remaining_today: 500, demo_call_remaining: true, bill_summary: billSummary, ticket_id: ticket.id });
    }

    // ── POST /payment/create ───────────────────────────────────
    if (endpoint === 'payment/create') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const session = sessions.get(sessionId);
      const body = await request.json();

      // Phase 10a: Enhanced itemized checkout
      const items: Array<{ name: string; quantity: number; unit_price: number; total: number }> = [];
      const variants = body.variants || [];
      for (const v of variants) {
        const price = Number(v.price_per_month || v.price || 999);
        const name = v.name || v.variant || 'PARWA Plan';
        items.push({ name, quantity: 1, unit_price: price, total: price });
      }
      const subtotal = items.reduce((sum, i) => sum + i.total, 0);
      const tax = Math.round(subtotal * 0.08 * 100) / 100;
      const total = subtotal + tax;

      const transactionId = `txn_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      const checkoutItems = Buffer.from(JSON.stringify({ items, subtotal, tax, total })).toString('base64url');
      const checkoutUrl = `https://pay.paddle.com/checkout/${transactionId}?items=${checkoutItems}&currency=USD`;

      // Store payment state in session context
      session.context.payment_data = {
        transaction_id: transactionId,
        checkout_url: checkoutUrl,
        items,
        subtotal,
        tax,
        total,
        currency: 'USD',
        status: 'pending',
        created_at: new Date().toISOString(),
      };
      session.payment_status = 'pending';
      session.detected_stage = 'payment';
      session.context.detected_stage = 'payment';

      // Phase 10e: Create action ticket for payment
      const ticket = createActionTicket(session, 'payment_variant', { transaction_id: transactionId, amount: total, items });

      // Add payment_card message
      const paymentCardMsg = {
        id: `payment_card_${Date.now()}`,
        session_id: sessionId,
        role: 'jarvis',
        content: `Payment initiated! Total: $${total.toFixed(2)}/mo. Redirecting to checkout...`,
        message_type: 'payment_card',
        metadata: {
          transaction_id: transactionId,
          checkout_url: checkoutUrl,
          amount: total,
          currency: 'USD',
          items,
          subtotal,
          tax,
          ticket_id: ticket.id,
        },
        timestamp: new Date().toISOString(),
      };
      session.messages.push(paymentCardMsg);

      session.updated_at = new Date().toISOString();
      saveSession(sessionId, session);
      return NextResponse.json({ checkout_url: checkoutUrl, transaction_id: transactionId, status: 'pending', amount: `$${total.toFixed(2)}/mo`, currency: 'USD', items, subtotal, tax, total, ticket_id: ticket.id });
    }

    // ── POST /demo-call/initiate ───────────────────────────────
    if (endpoint === 'demo-call/initiate') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId) {
        return NextResponse.json({ error: { code: 'bad_request', message: 'session_id required', details: null } }, { status: 400 });
      }
      const body = await request.json();
      // Phase 10e: Create action ticket for demo call
      let ticketId: string | undefined;
      if (sessionId && sessions.has(sessionId)) {
        const session = sessions.get(sessionId);
        const ticket = createActionTicket(session, 'demo_call', { phone: body.phone, duration_limit: 300 });
        ticketId = ticket.id;
        saveSession(sessionId, session);
      }
      return NextResponse.json({ call_id: `call_${Date.now()}`, status: 'initiated', phone: body.phone, duration_limit: 300, message: `Demo call initiated to ${body.phone}. You'll receive a call within 30 seconds.`, ticket_id: ticketId });
    }

    // ── POST /handoff ──────────────────────────────────────────
    if (endpoint === 'handoff') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const session = sessions.get(sessionId);
      session.handoff_completed = true;
      session.is_active = false; // Deactivate old onboarding session
      session.detected_stage = 'handoff';
      session.context.detected_stage = 'handoff';

      // Phase 10e: Create action ticket for handoff
      const ticket = createActionTicket(session, 'handoff', {
        session_duration: session.total_message_count,
        final_stage: session.detected_stage,
        email_verified: session.context.email_verified,
        payment_status: session.payment_status,
      });

      // Gap J8: Create new customer care session (per spec: type='customer_care',
      // selective context transfer — NO chat history, only business info)
      const careSession = createDefaultSession('handoff');
      careSession.type = 'customer_care';
      careSession.context.industry = session.context.industry;
      careSession.context.business_email = session.context.business_email;
      careSession.context.email_verified = session.context.email_verified;
      careSession.context.selected_variants = session.context.selected_variants;
      careSession.context.selected_plan = session.context.selected_plan;
      careSession.context.entry_source = 'handoff';
      careSession.context.handoff_from_session = sessionId;
      // Intentionally NOT transferring: messages, roi_result, concerns_raised, demo_topics

      const careWelcome = getContextAwareWelcome('handoff', careSession.context);
      const careWelcomeMsg = {
        id: `jarvis_welcome_${Date.now()}`,
        session_id: careSession.id,
        role: 'jarvis',
        content: careWelcome,
        message_type: 'handoff_card',
        metadata: {
          handoff_from: sessionId,
          handoff_at: new Date().toISOString(),
          ticket_id: ticket.id,
          transferred_fields: ['industry', 'business_email', 'selected_variants', 'selected_plan'],
        },
        timestamp: new Date().toISOString(),
      };
      careSession.messages.push(careWelcomeMsg);
      saveSession(careSession.id, careSession);

      // Add handoff_card to old session too
      const handoffCardMsg = {
        id: `handoff_card_${Date.now()}`,
        session_id: sessionId,
        role: 'jarvis',
        content: "You've been transferred to Customer Care. A specialist will take over from here with full context of your journey.",
        message_type: 'handoff_card',
        metadata: { new_session_id: careSession.id, ticket_id: ticket.id },
        timestamp: new Date().toISOString(),
      };
      session.messages.push(handoffCardMsg);

      session.updated_at = new Date().toISOString();
      saveSession(sessionId, session);
      return NextResponse.json({ handoff_completed: true, new_session_id: careSession.id, handoff_at: new Date().toISOString(), ticket_id: ticket.id });
    }

    // ── POST /context/entry — Update Entry Context ────────────
    if (endpoint === 'context/entry') {
      const body = await request.json();
      const { session_id, entry_source, entry_params } = body;

      if (!session_id || !sessions.has(session_id)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }

      const session = sessions.get(session_id);

      // Build enhanced context from entry params (Phase 9a)
      const params = entry_params || {};
      if (params.industry) session.context.industry = String(params.industry);
      if (params.utm_source) session.context.referral_source = String(params.utm_source);
      if (params.utm_medium) session.context.utm_medium = String(params.utm_medium);
      if (params.variant) {
        const variants = session.context.selected_variants || [];
        if (!variants.includes(String(params.variant))) variants.push(String(params.variant));
        session.context.selected_variants = variants;
      }
      if (params.plan) session.context.selected_plan = String(params.plan);
      if (params.referrer || params.ref) session.context.referrer = String(params.referrer || params.ref);

      if (entry_source) {
        session.context.entry_source = entry_source;
      }
      if (entry_params) {
        session.context.entry_params = { ...session.context.entry_params, ...params };
      }

      // Phase 8b: Generate context-aware welcome message
      const welcomeContent = getContextAwareWelcome(session.context.entry_source, session.context);

      const welcomeMsg = {
        id: `jarvis_entry_${Date.now()}`,
        session_id: session.id,
        role: 'jarvis',
        content: welcomeContent,
        message_type: 'text',
        metadata: { entry_source: session.context.entry_source, is_reentry: true },
        timestamp: new Date().toISOString(),
      };
      session.messages.push(welcomeMsg);
      session.updated_at = new Date().toISOString();
      saveSession(session.id, session);
      return NextResponse.json({ session, new_welcome: welcomeMsg });
    }

    // ── POST /payment/webhook — Simulated Paddle Webhook ─────────
    if (endpoint === 'payment/webhook') {
      const body = await request.json();
      const { session_id, event_type, transaction_id } = body;

      if (!session_id || !sessions.has(session_id)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }

      const session = sessions.get(session_id);

      if (event_type === 'payment.completed') {
        session.payment_status = 'completed';
        if (session.context.payment_data) {
          session.context.payment_data.status = 'completed';
          session.context.payment_data.completed_at = new Date().toISOString();
        }

        // Update payment ticket
        const paymentTickets = (session.context.action_tickets || []).filter((t: any) =>
          (t.type === 'payment_variant' || t.type === 'payment_demo_pack') && t.status !== 'completed'
        );
        if (paymentTickets.length > 0) {
          updateActionTicket(session, paymentTickets[paymentTickets.length - 1].id, { status: 'completed' });
        }

        // Add payment confirmation message
        const amount = session.context.payment_data?.total || 0;
        const confirmationMsg = {
          id: `payment_success_${Date.now()}`,
          session_id: session.id,
          role: 'jarvis',
          content: `Payment of $${amount.toFixed(2)} completed successfully! Welcome to PARWA. Setting up your account...`,
          message_type: 'payment_confirmation',
          metadata: {
            transaction_id: transaction_id || session.context.payment_data?.transaction_id,
            amount,
            currency: 'USD',
            status: 'completed',
          },
          timestamp: new Date().toISOString(),
        };
        session.messages.push(confirmationMsg);
      } else if (event_type === 'payment.failed') {
        session.payment_status = 'failed';
        if (session.context.payment_data) {
          session.context.payment_data.status = 'failed';
          session.context.payment_data.failed_at = new Date().toISOString();
        }

        // Update payment ticket
        const paymentTickets = (session.context.action_tickets || []).filter((t: any) =>
          (t.type === 'payment_variant' || t.type === 'payment_demo_pack') && t.status !== 'completed'
        );
        if (paymentTickets.length > 0) {
          updateActionTicket(session, paymentTickets[paymentTickets.length - 1].id, { status: 'failed' });
        }
      }

      session.updated_at = new Date().toISOString();
      saveSession(session.id, session);
      return NextResponse.json({ received: true, event_type, payment_status: session.payment_status });
    }

    // ── POST /tickets — Create Action Ticket ─────────────────────
    if (endpoint === 'tickets') {
      const body = await request.json();
      const { session_id, type, metadata } = body;

      if (!session_id || !sessions.has(session_id)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      if (!type) {
        return NextResponse.json({ error: { code: 'bad_request', message: 'Ticket type is required', details: null } }, { status: 400 });
      }

      const session = sessions.get(session_id);
      const ticket = createActionTicket(session, type, metadata || {});
      session.updated_at = new Date().toISOString();
      saveSession(session.id, session);
      return NextResponse.json(ticket, { status: 201 });
    }

    return NextResponse.json({ error: { code: 'not_found', message: `Unknown POST endpoint: /${endpoint}`, details: null } }, { status: 404 });
  } catch (error: unknown) {
    console.error('Jarvis API POST error:', error);
    const message = error instanceof Error ? error.message : 'Internal server error';
    return NextResponse.json({ error: { code: 'internal_error', message, details: null } }, { status: 500 });
  }
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const endpoint = path.join('/');
  const url = new URL(request.url);

  try {
    // ── GET /session ──────────────────────────────────────────
    if (endpoint === 'session') {
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      return NextResponse.json(sessions.get(sessionId));
    }

    // ── GET /history ───────────────────────────────────────────
    if (endpoint === 'history') {
      const sessionId = url.searchParams.get('session_id');
      const limit = parseInt(url.searchParams.get('limit') || '100', 10);
      const offset = parseInt(url.searchParams.get('offset') || '0', 10);

      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json({ messages: [], total: 0, limit, offset, has_more: false });
      }

      const session = sessions.get(sessionId)!;
      const allMessages = session.messages;
      const paged = allMessages.slice(offset, offset + limit);
      return NextResponse.json({ messages: paged, total: allMessages.length, limit, offset, has_more: offset + limit < allMessages.length });
    }

    // ── GET /demo-pack/status ─────────────────────────────────
    if (endpoint === 'demo-pack/status') {
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const session = sessions.get(sessionId)!;
      return NextResponse.json({ pack_type: session.pack_type, remaining_today: session.remaining_today, total_allowed: session.pack_type === 'demo' ? 500 : 20, pack_expiry: session.pack_type === 'demo' ? new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString() : null, demo_call_remaining: !session.context.demo_call_used });
    }

    // ── GET /payment/status — Payment Status Check ───────────────
    if (endpoint === 'payment/status') {
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const session = sessions.get(sessionId)!;
      const paymentData = session.context.payment_data;
      return NextResponse.json({
        payment_status: session.payment_status,
        transaction_id: paymentData?.transaction_id || null,
        checkout_url: paymentData?.checkout_url || null,
        amount: paymentData?.total || 0,
        currency: paymentData?.currency || 'USD',
        items: paymentData?.items || [],
        subtotal: paymentData?.subtotal || 0,
        tax: paymentData?.tax || 0,
        created_at: paymentData?.created_at || null,
        completed_at: paymentData?.completed_at || null,
        bill_summary: session.context.bill_summary || null,
      });
    }

    // ── GET /tickets — List Session Tickets ──────────────────────
    if (endpoint === 'tickets') {
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const session = sessions.get(sessionId)!;
      const tickets = session.context.action_tickets || [];
      const typeFilter = url.searchParams.get('type');
      const statusFilter = url.searchParams.get('status');
      const filtered = tickets.filter((t: any) => {
        if (typeFilter && t.type !== typeFilter) return false;
        if (statusFilter && t.status !== statusFilter) return false;
        return true;
      });
      return NextResponse.json({ tickets: filtered, total: filtered.length });
    }

    // ── GET /tickets/:id — Get Specific Ticket ───────────────────
    if (endpoint.startsWith('tickets/') && endpoint.split('/').length === 2) {
      const ticketId = endpoint.split('/')[1];
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const session = sessions.get(sessionId)!;
      const tickets = session.context.action_tickets || [];
      const ticket = tickets.find((t: any) => t.id === ticketId);
      if (!ticket) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Ticket not found', details: null } }, { status: 404 });
      }
      return NextResponse.json(ticket);
    }

    return NextResponse.json({ error: { code: 'not_found', message: `Unknown GET endpoint: /${endpoint}`, details: null } }, { status: 404 });
  } catch (error: unknown) {
    console.error('Jarvis API GET error:', error);
    const message = error instanceof Error ? error.message : 'Internal server error';
    return NextResponse.json({ error: { code: 'internal_error', message, details: null } }, { status: 500 });
  }
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const endpoint = path.join('/');
  const url = new URL(request.url);

  try {
    // ── PATCH /context ────────────────────────────────────────
    if (endpoint === 'context') {
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const body = await request.json();
      const session = sessions.get(sessionId)!;
      session.context = { ...session.context, ...body };
      session.updated_at = new Date().toISOString();
      saveSession(sessionId, session);
      return NextResponse.json(session);
    }

    // ── PATCH /tickets/:id/status — Update Ticket Status ────────
    if (endpoint.startsWith('tickets/') && endpoint.endsWith('/status') && endpoint.split('/').length === 3) {
      const parts = endpoint.split('/');
      const ticketId = parts[1];
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const body = await request.json();
      const session = sessions.get(sessionId)!;
      const updated = updateActionTicket(session, ticketId, { status: body.status, metadata: body.metadata });
      if (!updated) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Ticket not found', details: null } }, { status: 404 });
      }
      session.updated_at = new Date().toISOString();
      saveSession(sessionId, session);
      return NextResponse.json(updated);
    }

    return NextResponse.json({ error: { code: 'not_found', message: `Unknown PATCH endpoint: /${endpoint}`, details: null } }, { status: 404 });
  } catch (error: unknown) {
    console.error('Jarvis API PATCH error:', error);
    const message = error instanceof Error ? error.message : 'Internal server error';
    return NextResponse.json({ error: { code: 'internal_error', message, details: null } }, { status: 500 });
  }
}
