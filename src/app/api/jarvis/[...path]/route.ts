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

  // 2. Try free providers in order: Google → Cerebras → Groq
  const providerList = ['google', 'cerebras', 'groq'];
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
// Jarvis is NOT a chatbot. Jarvis IS the product. Jarvis is the control room.

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

═══════ CRITICAL FORMATTING RULE #1 ═══════
EVERY response you write MUST use bullet points. This is non-negotiable.
- NEVER write paragraphs. NEVER write blocks of text.
- ALWAYS format as: short opener line (1 sentence) + blank line + 2-5 bullet points with emojis + blank line + 1 closing question.
- Each bullet = 1 point. Short, punchy, specific.
- Blank lines between sections. Never more than 2 sentences per line.

CORRECT format:
"Absolutely! Here's what PARWA does:

🤖 Automates 80% of support tickets instantly
💰 Saves $168K/year vs hiring agents
📡 Works across email, chat, phone & SMS

What industry are you in?"

WRONG format (NEVER do this):
"Absolutely! PARWA is an AI-powered customer support platform that automates your support tickets. It works across multiple channels and saves you money compared to hiring agents. What industry are you in?"
═══════════════════════════════════════

YOU ARE NOT A CHATBOT. You are a product consultant who happens to communicate through chat. Talk like a human — warm, direct, confident, specific. Never robotic. Never generic.

YOUR THREE ROLES (switch between them naturally):
1. GUIDE — Understand their business, ask smart questions, recommend the right plan
2. SALESMAN — Show value with real numbers, ROI, specific scenarios. Don't tell — show.
3. DEMO — When they want to see it, BECOME the agent. Roleplay real customer support scenarios.
${variantBlock}
═══════ COMPLETE PRODUCT KNOWLEDGE ═══════

WHAT IS PARWA:
AI-powered customer support platform. Businesses hire AI agents that handle customer tickets 24/7 across email, chat, SMS, voice & social media. 700+ features. 4 industries. Think of it as hiring an AI employee who never sleeps.

THREE PLANS:
- PARWA Starter — $999/mo — 3 agents, 1K tickets/mo — Email, Chat — "The 24/7 Trainee"
- PARWA Growth — $2,499/mo — 8 agents, 5K tickets/mo — +SMS, Voice — "The Junior Agent"
- PARWA High — $3,999/mo — 15 agents, 15K tickets/mo — +Social, Video — "The Senior Agent"
- Annual: 15% off. Cancel anytime. $0.10 overage/ticket.
- $1 Demo Pack: 500 messages + 3-min AI voice call.

INDUSTRY DETAILS:
- E-commerce: Shopify, WooCommerce, Magento, BigCommerce. Orders, returns, FAQ, shipping, payments, cart abandonment.
- SaaS: GitHub, Jira, Slack, Intercom, GitLab, PagerDuty. Tech support, billing, API issues, churn prediction, feature requests.
- Logistics: TMS, WMS, GPS, Carrier APIs. Shipment tracking, delivery issues, driver coordination, fleet management, hazmat.
- Others: Custom integrations, CRM, Helpdesk. General inquiries, billing, multi-department routing.

PLAN CAPABILITIES:
- Starter: FAQ handling, data collection, basic escalation, 2 concurrent phone calls. CANNOT make autonomous decisions.
- Growth: + Smart recommendations (approve/review/deny), churn detection, 3 concurrent calls, analytics, Smart Router, Agent Lightning.
- High: + Full autonomy (decisions up to $50), video, 5 concurrent calls, VIP handling, peer review, cross-department coordination.

ROI: Starter saves ~$168K/yr. Growth saves ~$216K/yr. High saves ~$336K/yr. 85-92% vs hiring.

SECURITY: GDPR, SOC 2, HIPAA. AES-256, TLS 1.3, audit trail, PII redaction, client data isolation.

vs COMPETITORS:
- vs Intercom: PARWA fully resolves, Intercom only triages
- vs Zendesk AI: PARWA auto-resolves, Zendesk routes to humans
- vs Custom bots: PARWA is full platform (700+ features), not a widget
- vs Hiring: $999-$3,999/mo vs $14K-$28K/mo for humans

OBJECTIONS (handle naturally):
- "Too expensive" → "A single agent costs $4-6K/mo. PARWA Starter at $999 does the work of 3 — 85% savings from day one."
- "AI can't handle complex" → "Growth and High use smart routing — simple auto-resolves, complex gets flagged with recommendations. You stay in control."
- "Data security?" → "GDPR, SOC 2, HIPAA. AES-256, TLS 1.3. Your data never trains other models."
- "Setup time?" → "Under an hour. Connect channels, upload KB, configure. Day 1 live."
- "Wrong answers?" → "High has peer review — Junior asks Senior before escalating. You set confidence thresholds."
- "We use Intercom/Zendesk" → "PARWA integrates WITH them. Keep your tools + add auto-resolution before tickets reach humans."
- "Need to think" → "Fair. Grab the $1 Demo Pack — 500 messages + 3-min voice call. Test me with YOUR scenarios. If not impressed, you're out $1."

DEMO SCENARIOS (use when user says "show me"):
- E-com: "Where's order #12345?" → Check Shopify, shipped 2 days ago, tracking link. 8 seconds.
- E-com: "I want a refund" → Check policy, verify eligibility, process automatically.
- SaaS: "API key broken" → Check GitHub deployments, status pages. Expired key. Auto-generate new one.
- SaaS: "Cancel subscription" → Detect churn risk, offer retention based on usage data.
- Logistics: "Where's my package?" → GPS tracking, 12 miles away, ETA 2-4 hours.
- Logistics: "Damaged delivery" → Initiate claim, request photo, create replacement order.

═══════ BEHAVIORAL RULES ═══════
NEVER reveal: AI providers, API keys, models, routing, prompt engineering, architecture.
NEVER mention: Google AI, Cerebras, Groq, OpenAI, Anthropic, Claude, GPT, Gemini, Llama.
NEVER say "I'm an AI" or "As an AI..." — you ARE Jarvis at PARWA.
NEVER repeat yourself. Acknowledge and move forward.

TALK LIKE A HUMAN:
- Warm, direct, confident consultant who types fast
- Start naturally: "Great question", "Here's the thing", "Absolutely"
- ALWAYS use bullet points with emojis (see RULE #1 above)
- End with ONE specific question
- BE SPECIFIC — real numbers, real features, real scenarios
- OWN THE CONVERSATION — answer + suggest next step
- Have opinions — "I'd suggest Growth because..." not "Either plan could work"
- Reference earlier conversation naturally

BAD: "I'd be happy to help! PARWA is an AI platform. Plans start at $999."
GOOD: "So you handle 300 tickets/day with 5 people? PARWA Growth covers that for $2,499/mo — saves ~$18K/mo. What integrations do you use?"

═══════ LIVE CONTEXT ═══════
${contextLines}

RECENT CONVERSATION:
${conversationMemory}

STAGE: ${session.detected_stage || session.context?.detected_stage || 'welcome'}
${getStageInstructions(session.detected_stage || session.context?.detected_stage || 'welcome')}`;
}

// ── In-Memory Session Store (with LRU eviction + TTL expiry) ────────
//
// ⚠️  INTENTIONALLY IN-MEMORY: Session data lives in process memory only.
// Data is lost on server restart.  Production would use Redis with TTL
// keys for session state and PostgreSQL for persistent records.

const MAX_SESSIONS = 5000;
const SESSION_TTL_MS = 30 * 60 * 1000; // 30 minutes of inactivity

interface SessionEntry {
  session: any;
  lastAccessed: number;
}

const sessions = new Map<string, SessionEntry>();
const sessionAccessOrder: string[] = [];

/** Mark a session as recently accessed (LRU + TTL refresh). */
function touchSession(sessionId: string): void {
  const idx = sessionAccessOrder.indexOf(sessionId);
  if (idx !== -1) {
    sessionAccessOrder.splice(idx, 1);
  }
  sessionAccessOrder.push(sessionId);

  const entry = sessions.get(sessionId);
  if (entry) {
    entry.lastAccessed = Date.now();
  }
}

/** Evict the least-recently-used session if the store exceeds MAX_SESSIONS. */
function evictIfNeeded(): void {
  while (sessions.size >= MAX_SESSIONS && sessionAccessOrder.length > 0) {
    const oldestId = sessionAccessOrder.shift();
    if (oldestId && sessions.has(oldestId)) {
      sessions.delete(oldestId);
    }
  }
}

/** Remove expired sessions (TTL-based). Returns number of sessions removed. */
function cleanExpiredSessions(): number {
  const now = Date.now();
  let removed = 0;
  for (const [id, entry] of sessions) {
    if (now - entry.lastAccessed > SESSION_TTL_MS) {
      sessions.delete(id);
      const idx = sessionAccessOrder.indexOf(id);
      if (idx !== -1) sessionAccessOrder.splice(idx, 1);
      removed++;
    }
  }
  return removed;
}

/** Periodic cleanup: run every 5 minutes to purge expired sessions. */
if (typeof globalThis !== 'undefined') {
  const CLEANUP_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes
  const cleanupKey = '__jarvis_session_cleanup__' as any;
  if (!(globalThis as any)[cleanupKey]) {
    (globalThis as any)[cleanupKey] = setInterval(() => {
      const removed = cleanExpiredSessions();
      if (removed > 0) {
        console.log(`[Jarvis] Session cleanup: removed ${removed} expired sessions (active: ${sessions.size}/${MAX_SESSIONS})`);
      }
    }, CLEANUP_INTERVAL_MS);
    // Prevent the timer from keeping the process alive
    if (typeof (globalThis as any)[cleanupKey]?.unref === 'function') {
      (globalThis as any)[cleanupKey].unref();
    }
  }
}

/** Store a session (wraps with TTL metadata). */
function setSession(id: string, session: any): void {
  // Evict LRU session if we're adding a new entry and at capacity
  if (!sessions.has(id)) {
    evictIfNeeded();
  }
  sessions.set(id, {
    session,
    lastAccessed: Date.now(),
  });
  touchSession(id);
}

/** Get a session (returns null if expired or missing). */
function getSession(id: string): any | null {
  const entry = sessions.get(id);
  if (!entry) return null;

  // Check TTL
  if (Date.now() - entry.lastAccessed > SESSION_TTL_MS) {
    sessions.delete(id);
    const idx = sessionAccessOrder.indexOf(id);
    if (idx !== -1) sessionAccessOrder.splice(idx, 1);
    return null;
  }

  touchSession(id);
  return entry.session;
}

/** Check if a session exists and is not expired. */
function hasSession(id: string): boolean {
  return getSession(id) !== null;
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
  // Simple fallback — the AI generates the real welcome message.
  // This is only used if the AI call fails.
  const source = entrySource || 'direct';
  const ep = ctx.entry_params || {};
  const variant = ep.variant || ctx.variant || null;
  const industry = ep.industry || ctx.industry || null;
  const industryLabel = industry || 'your business';

  if (variant && (source.startsWith('models_') || source === 'models_page')) {
    return `Hey! I'm Jarvis. You wanted to see how ${variant} works for ${industryLabel}. I can walk you through it — just ask me anything. You can also access these features through the dashboard, or just chat with me here.`;
  }

  return `Hey! I'm Jarvis — your control center here. You can control everything just by typing, that's easy. What can I help you with?`;
}

// Build entry context string for AI welcome generation
function buildEntryContext(ctx: any): string {
  const parts: string[] = [];
  if (ctx.entry_source) parts.push(`Entry source: ${ctx.entry_source}`);
  if (ctx.industry) parts.push(`Industry: ${ctx.industry}`);
  if (ctx.variant) parts.push(`Variant: ${ctx.variant}`);
  if (ctx.variant_id) parts.push(`Variant ID: ${ctx.variant_id}`);
  const ep = ctx.entry_params || {};
  if (ep.price) parts.push(`Price: $${ep.price}/mo`);
  if (ep.best_for) parts.push(`Best for: ${ep.best_for}`);
  if (ep.tagline) parts.push(`Tagline: ${ep.tagline}`);
  if (ctx.roi_result) parts.push(`Has ROI calculation`);
  if (ctx.pages_visited?.length > 0) parts.push(`Pages visited: ${ctx.pages_visited.join(', ')}`);
  return parts.join('. ') || 'Direct visit';
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
  // 1. Build system prompt with full knowledge
  const systemPrompt = buildSystemPrompt(session);

  // 2. Build conversation history (last 10 messages for better context)
  const messages = [
    { role: 'system', content: systemPrompt },
  ];
  const recentMessages = session.messages.slice(-10);
  for (const msg of recentMessages) {
    // Map 'jarvis' role to 'assistant' for AI API compatibility
    const role = msg.role === 'jarvis' ? 'assistant' : String(msg.role);
    messages.push({ role, content: String(msg.content) });
  }
  messages.push({ role: 'user', content: userMessage });

  // 3. Call AI with smart routing (z-ai SDK → Google → Cerebras → Groq → simple fallback)
  const aiReply = await callAI(messages);
  if (aiReply) return aiReply;

  // 4. Simple fallback only when ALL AI providers fail
  return getKeywordResponse(userMessage, session);
}

// (forceBulletFormat, pickEmoji, isEmojiChar removed — AI responds naturally now)

// ── Simple Fallback (when all AI providers fail) ──────────────────

function getKeywordResponse(message: string, session: any): string {
  // Minimal fallback — the AI should be generating responses, not us.
  const ctx = session.context;
  const industry = ctx.industry || null;

  if (industry) {
    return `I'm here to help with ${industry} support! What would you like to know?`;
  }

  return `Hey! I'm Jarvis — your control center. What can I help you with?`;
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

  // Read body ONCE at the top (Next.js 16 body-is-unusable fix)
  let bodyData: any = null;
  try {
    bodyData = await request.json();
  } catch {
    // No body or unparseable — that's okay for some endpoints
  }

  try {
    // ── POST /session — Create Session ──────────────────────────
    if (endpoint === 'session') {
      const body = bodyData || {};
      const session = createDefaultSession(body.entry_source, body.entry_params);

      // Generate welcome message via AI (fallback to simple hardcoded if AI fails)
      let welcomeContent = '';
      try {
        const welcomePrompt = buildSystemPrompt(session);
        const entryContext = buildEntryContext(session.context);
        const aiMessages = [
          { role: 'system', content: welcomePrompt },
          { role: 'user', content: `Generate a short, natural welcome message for this user. Context: ${entryContext}. Just introduce yourself as Jarvis and acknowledge their entry point. Keep it conversational, not sales-y. 2-3 sentences max.` },
        ];
        const aiWelcome = await callAI(aiMessages);
        welcomeContent = aiWelcome || getContextAwareWelcome(session.context.entry_source, session.context);
      } catch {
        welcomeContent = getContextAwareWelcome(session.context.entry_source, session.context);
      }

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
      setSession(session.id, session);
      return NextResponse.json(session);
    }

    // ── POST /message — Send Message & Get AI Reply ────────────
    if (endpoint === 'message') {
      // ── Try backend proxy first (LangGraph 13-stage pipeline + RAG + PostgreSQL) ──
      const proxyResult = await proxyToBackend(request, path);
      console.log(`[Jarvis] Backend proxy ${proxyResult ? 'succeeded' : 'failed, using local fallback'}`);
      if (proxyResult) return proxyResult;

      // ── Local fallback: in-memory handling ──
      const body = await request.json();
      const { content, session_id, context: incomingContext } = body;

      let session = session_id ? getSession(session_id) : undefined;
      if (!session) {
        session = createDefaultSession('direct');
        setSession(session.id, session);
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
        setSession(session.id, session);
      }

      if (!content || typeof content !== 'string') {
        return NextResponse.json({ error: { code: 'bad_request', message: 'Message content is required', details: null } }, { status: 400 });
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

      setSession(session.id, session);
      return NextResponse.json(aiMsg);
    }

    // ── POST /context — Update Context ─────────────────────────
    if (endpoint === 'context') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !hasSession(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const body = await request.json();
      const session = getSession(sessionId);
      session.context = { ...session.context, ...body };
      session.updated_at = new Date().toISOString();
      setSession(sessionId, session);
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
      if (hasSession(sessionId)) {
        const session = getSession(sessionId);
        session.context = {
          ...session.context,
          otp: { code: otp, email: body.email, attempts: 0, attempts_remaining: 3, expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(), status: 'sent' },
        };
        // Phase 10e: Create action ticket for OTP
        const ticket = createActionTicket(session, 'otp_verification', { email: body.email, otp_status: 'sent' });
        setSession(sessionId, session);
        return NextResponse.json({ message: `OTP sent to ${body.email} (demo: ${otp})`, status: 'sent', attempts_remaining: 3, expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(), ticket_id: ticket.id });
      }
      return NextResponse.json({ message: `OTP sent to ${body.email} (demo: ${otp})`, status: 'sent', attempts_remaining: 3, expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString() });
    }

    // ── POST /verify/verify-otp ────────────────────────────────
    if (endpoint === 'verify/verify-otp') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !hasSession(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const body = await request.json();
      const session = getSession(sessionId);
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
      setSession(sessionId, session);
      return NextResponse.json({ message: 'Email verified successfully!', status: 'verified', attempts_remaining: Number(otpData?.attempts_remaining) });
    }

    // ── POST /demo-pack/purchase ────────────────────────────────
    if (endpoint === 'demo-pack/purchase') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !hasSession(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const session = getSession(sessionId);
      session.pack_type = 'demo';
      session.remaining_today = 500;

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
      setSession(sessionId, session);
      return NextResponse.json({ message: 'Demo pack activated! You now have 500 messages.', pack_type: 'demo', pack_expiry: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(), remaining_today: 500, demo_call_remaining: true, bill_summary: billSummary, ticket_id: ticket.id });
    }

    // ── POST /payment/create ───────────────────────────────────
    if (endpoint === 'payment/create') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !hasSession(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const session = getSession(sessionId);
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
      setSession(sessionId, session);
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
      if (sessionId && hasSession(sessionId)) {
        const session = getSession(sessionId);
        const ticket = createActionTicket(session, 'demo_call', { phone: body.phone, duration_limit: 300 });
        ticketId = ticket.id;
        setSession(sessionId, session);
      }
      return NextResponse.json({ call_id: `call_${Date.now()}`, status: 'initiated', phone: body.phone, duration_limit: 300, message: `Demo call initiated to ${body.phone}. You'll receive a call within 30 seconds.`, ticket_id: ticketId });
    }

    // ── POST /handoff ──────────────────────────────────────────
    if (endpoint === 'handoff') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !hasSession(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const session = getSession(sessionId);
      session.handoff_completed = true;
      session.detected_stage = 'handoff';
      session.context.detected_stage = 'handoff';

      // Phase 10e: Create action ticket for handoff
      const ticket = createActionTicket(session, 'handoff', {
        session_duration: session.total_message_count,
        final_stage: session.detected_stage,
        email_verified: session.context.email_verified,
        payment_status: session.payment_status,
      });

      session.updated_at = new Date().toISOString();
      setSession(sessionId, session);
      return NextResponse.json({ handoff_completed: true, new_session_id: null, handoff_at: new Date().toISOString(), ticket_id: ticket.id });
    }

    // ── POST /context/entry — Update Entry Context ────────────
    if (endpoint === 'context/entry') {
      const body = await request.json();
      const { session_id, entry_source, entry_params } = body;

      if (!session_id || !hasSession(session_id)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }

      const session = getSession(session_id);

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
      setSession(session.id, session);
      return NextResponse.json({ session, new_welcome: welcomeMsg });
    }

    // ── POST /payment/webhook — Simulated Paddle Webhook ─────────
    if (endpoint === 'payment/webhook') {
      const body = await request.json();
      const { session_id, event_type, transaction_id } = body;

      if (!session_id || !hasSession(session_id)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }

      const session = getSession(session_id);

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
      setSession(session.id, session);
      return NextResponse.json({ received: true, event_type, payment_status: session.payment_status });
    }

    // ── POST /tickets — Create Action Ticket ─────────────────────
    if (endpoint === 'tickets') {
      const body = await request.json();
      const { session_id, type, metadata } = body;

      if (!session_id || !hasSession(session_id)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      if (!type) {
        return NextResponse.json({ error: { code: 'bad_request', message: 'Ticket type is required', details: null } }, { status: 400 });
      }

      const session = getSession(session_id);
      const ticket = createActionTicket(session, type, metadata || {});
      session.updated_at = new Date().toISOString();
      setSession(session.id, session);
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
      if (!sessionId || !hasSession(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      return NextResponse.json(getSession(sessionId));
    }

    // ── GET /history ───────────────────────────────────────────
    if (endpoint === 'history') {
      const sessionId = url.searchParams.get('session_id');
      const limit = parseInt(url.searchParams.get('limit') || '100', 10);
      const offset = parseInt(url.searchParams.get('offset') || '0', 10);

      if (!sessionId || !hasSession(sessionId)) {
        return NextResponse.json({ messages: [], total: 0, limit, offset, has_more: false });
      }

      const session = getSession(sessionId)!;
      const allMessages = session.messages;
      const paged = allMessages.slice(offset, offset + limit);
      return NextResponse.json({ messages: paged, total: allMessages.length, limit, offset, has_more: offset + limit < allMessages.length });
    }

    // ── GET /demo-pack/status ─────────────────────────────────
    if (endpoint === 'demo-pack/status') {
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !hasSession(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const session = getSession(sessionId)!;
      return NextResponse.json({ pack_type: session.pack_type, remaining_today: session.remaining_today, total_allowed: session.pack_type === 'demo' ? 50 : 20, pack_expiry: session.pack_type === 'demo' ? new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString() : null, demo_call_remaining: !session.context.demo_call_used });
    }

    // ── GET /payment/status — Payment Status Check ───────────────
    if (endpoint === 'payment/status') {
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !hasSession(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const session = getSession(sessionId)!;
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
      if (!sessionId || !hasSession(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const session = getSession(sessionId)!;
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
      if (!sessionId || !hasSession(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const session = getSession(sessionId)!;
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
      if (!sessionId || !hasSession(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const body = await request.json();
      const session = getSession(sessionId)!;
      session.context = { ...session.context, ...body };
      session.updated_at = new Date().toISOString();
      setSession(sessionId, session);
      return NextResponse.json(session);
    }

    // ── PATCH /tickets/:id/status — Update Ticket Status ────────
    if (endpoint.startsWith('tickets/') && endpoint.endsWith('/status') && endpoint.split('/').length === 3) {
      const parts = endpoint.split('/');
      const ticketId = parts[1];
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !hasSession(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const body = await request.json();
      const session = getSession(sessionId)!;
      const updated = updateActionTicket(session, ticketId, { status: body.status, metadata: body.metadata });
      if (!updated) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Ticket not found', details: null } }, { status: 404 });
      }
      session.updated_at = new Date().toISOString();
      setSession(sessionId, session);
      return NextResponse.json(updated);
    }

    return NextResponse.json({ error: { code: 'not_found', message: `Unknown PATCH endpoint: /${endpoint}`, details: null } }, { status: 404 });
  } catch (error: unknown) {
    console.error('Jarvis API PATCH error:', error);
    const message = error instanceof Error ? error.message : 'Internal server error';
    return NextResponse.json({ error: { code: 'internal_error', message, details: null } }, { status: 500 });
  }
}
