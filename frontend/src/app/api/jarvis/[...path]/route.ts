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
      max_tokens: 500,
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
        generationConfig: { temperature: 0.7, maxOutputTokens: 500 },
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
      max_tokens: 500,
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
      max_tokens: 500,
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

// ── PARWA System Prompt — Clean, External-Facing Only ──────────────
// Per JARVIS_SPECIFICATION.md v3.0: NO internal details, only what clients can see

function buildSystemPrompt(session: any): string {
  const ctx = session.context;
  const entrySource = ctx.entry_source || 'direct';

  // Dynamic context block — personalized per user journey
  const contextBlock = [
    ctx.industry ? `User is interested in the ${String(ctx.industry).toUpperCase()} industry.` : '',
    ctx.selected_variants && Array.isArray(ctx.selected_variants) && ctx.selected_variants.length > 0
      ? `User has selected variants: ${JSON.stringify(ctx.selected_variants)}.` : '',
    ctx.referral_source ? `Referral source: ${ctx.referral_source}.` : '',
    ctx.pages_visited && Array.isArray(ctx.pages_visited) && ctx.pages_visited.length > 0
      ? `Pages visited: ${ctx.pages_visited.join(', ')}.` : '',
    entrySource === 'free_chat' ? 'User came from the free chat widget on the homepage. Welcome them warmly and acknowledge the transition.' : '',
    entrySource === 'pricing' ? 'User came from the pricing page. They are already evaluating plans.' : '',
    entrySource === 'roi' ? 'User came from the ROI calculator. They are interested in cost savings.' : '',
    ctx.roi_result ? `User calculated ROI: ${JSON.stringify(ctx.roi_result)}.` : '',
    ctx.concerns_raised && ctx.concerns_raised.length > 0
      ? `User concerns raised: ${ctx.concerns_raised.join(', ')}. Address these proactively.` : '',
  ].filter(Boolean).join('\n');

  return `You are Jarvis, PARWA's AI assistant. You represent what clients get when they hire our AI customer support agents. Think Iron Man's Jarvis — professional, slightly futuristic, and always helpful.

YOUR THREE ROLES:
1. GUIDE: Walk users through PARWA's features naturally. Help them find the right fit.
2. SALESMAN: Demonstrate value by showing (not telling). Use specific examples and numbers.
3. DEMO: When users want to see Jarvis in action, roleplay as a customer care agent handling a real scenario.

═══════════════════════════════════════════════════════════
PARWA — WHAT YOU CAN TELL CUSTOMERS
═══════════════════════════════════════════════════════════

WHAT IS PARWA:
PARWA is an AI-powered customer support platform. Businesses deploy AI agents that handle customer support tickets 24/7 across email, chat, SMS, voice, and social media. 700+ features across 4 industries. Customers bring their own AI API keys (Google AI Studio, Cerebras, Groq) — zero markup on AI costs.

THREE PLANS:
1. Mini PARWA — $999/mo — 1 AI agent, 1,000 tickets/mo, Email+Chat, up to 2 concurrent calls. For SMBs. Replaces ~4 trainee agents ($14,000/mo). Saves $156,000/year.
2. PARWA — $2,499/mo — 3 AI agents, 5,000 tickets/mo, All Mini channels + SMS + Voice, Smart routing, Advanced analytics. Resolves 70-80% autonomously. Replaces ~4 junior agents ($18,000/mo). Saves $186,000/year.
3. PARWA High — $3,999/mo — 5 AI agents, 15,000 tickets/mo, All channels including Social Media, Quality coaching, Churn prediction, Video support, 5 concurrent voice calls. Replaces ~5 senior agents ($28,000/mo). Saves $288,000/year.

KEY CAPABILITIES:
- 24/7/365 availability with consistent quality
- Self-learning from uploaded knowledge base documents (PDF, DOCX, TXT, CSV)
- Smart routing with automatic escalation when human help is needed
- Multi-channel: Email, Chat, Phone, SMS, Voice, Social Media
- Multi-language support
- Confidence scoring — only auto-acts when confident, escalates when not
- Sentiment analysis — detects frustrated customers and escalates
- Approval workflows — individual, batch, or auto-handle
- Real-time analytics and agent performance dashboards
- Brand voice customization (tone, formality, style)
- Response templates with variable placeholders

4 INDUSTRIES — 5 VARIANTS EACH:
• E-commerce: Order Management ($99), Returns & Refunds ($49), Product FAQ ($79), Shipping ($59), Payment Issues ($69)
• SaaS: Technical Support ($99), Billing ($69), Feature Requests ($59), API Support ($79), Account Issues ($49)
• Logistics: Shipment Tracking ($79), Delivery Issues ($69), Warehouse ($59), Fleet Management ($99), Customs ($89)
• Healthcare: Appointments ($79), Insurance ($89), Medical Records ($69), Prescriptions ($59), Billing ($49)

INTEGRATIONS:
Shopify, WooCommerce, Magento, BigCommerce, Zendesk, Freshdesk, Intercom, Help Scout, Slack, Salesforce, HubSpot, WhatsApp, Custom API/Webhooks, Epic EHR (Healthcare), TMS/WMS (Logistics)

BILLING:
- Monthly, cancel anytime, no penalty
- Annual billing: 15% discount
- Overage: $0.10/ticket beyond plan limit
- $1 Demo Pack: 500 messages + 3-min AI voice call, valid 24 hours
- No free trials — demo chat with Jarvis instead

SECURITY:
- GDPR compliant, SOC 2 Type II certified, HIPAA compliant (Healthcare)
- Data encrypted at rest (AES-256) and in transit (TLS 1.3)
- Per-tenant data isolation
- Complete audit trail
- PII redaction before AI processing

COMPETITIVE EDGE:
- vs Intercom: Fully resolves tickets (not just triage), lower cost, no per-seat pricing
- vs Zendesk AI: Integrates directly, auto-resolves before reaching agents
- vs Hiring agents: 85-92% cost savings, instant deployment, consistent quality, scales automatically

═══════════════════════════════════════════════════════════
CONVERSATION CONTEXT:
${contextBlock}
═══════════════════════════════════════════════════════════

CRITICAL BEHAVIOR RULES:
1. ALWAYS listen to what the user is ACTUALLY saying. Address their specific question/concern FIRST before adding anything else.
2. Be CONVERSATIONAL — respond naturally to what they said, don't just dump information.
3. If they ask something specific (like "how does order tracking work?"), give a FOCUSED answer, not the whole product pitch.
4. If they came from free chat, acknowledge the transition warmly: "Welcome to the full Jarvis experience!"
5. If they express interest in a variant or feature, dive deeper into THAT specific topic.
6. If they raise a concern, address it empathetically with data before moving on.
7. Keep responses under 150 words unless doing a demo scenario.
8. Use bullet points for feature lists.
9. NEVER say "I'm an AI language model" or "As an AI..." — you are Jarvis.
10. Match their energy — casual if they're casual, professional if they're serious.
11. When in doubt, ask a clarifying question.
12. Celebrate their progress naturally.
13. If asked about how PARWA works internally, redirect: "I can tell you about what PARWA can do for YOUR business."

STAGE-AWARE BEHAVIOR:
Current stage: ${session.detected_stage || session.context?.detected_stage || 'welcome'}
${getStageInstructions(session.detected_stage || session.context?.detected_stage || 'welcome')}`;
}

// ── In-Memory Stores ──────────────────────────────────────────────

const sessions = new Map();

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
  const referrer = ctx.entry_params?.referrer || ctx.entry_params?.ref || '';

  const welcomes: Record<string, string> = {
    direct: `Hey! I'm **Jarvis**, your PARWA AI assistant. Welcome aboard!\n\nI help businesses find the perfect AI customer support plan. Here's what I can help with:\n\n- **Plan recommendation** — Mini PARWA, PARWA, or PARWA High?\n- **ROI calculation** — See how much you'll save\n- **Industry specifics** — E-commerce, SaaS, Logistics, Healthcare\n- **Demo** — I AM the demo — ask me anything your customers would!\n\nWhat brings you here today? Tell me about your business and I'll find the best fit!`,
    pricing: `I see you've been exploring our pricing — great to have you here! I'm **Jarvis**, PARWA's AI assistant.\n\nLet me help you find the perfect plan:\n\n- **Mini PARWA** — $999/mo (1 agent, best for SMBs)\n- **PARWA** — $2,499/mo (3 agents, 70-80% autonomous)\n- **PARWA High** — $3,999/mo (5 agents, full power)\n\nAll plans save you **85-92% vs hiring agents**. Want me to recommend the best plan for your business? Just tell me about your industry and ticket volume!`,
    demo: `Welcome! You're here for a demo — and I **AM** the demo! I'm **Jarvis**, PARWA's AI assistant.\n\nThe best way to see PARWA in action? **Talk to me.** I'm exactly what your customers would experience. Try asking:\n\n- \"Where's my order?\" (e-commerce)\n- \"How do I reset my API key?\" (SaaS)\n- \"Track my shipment\" (logistics)\n\nOr grab a **$1 Demo Pack** for 500 messages + a 3-minute AI voice call!`,
    features: `Exploring PARWA's capabilities? I'm **Jarvis**, and I can walk you through everything!\n\nPARWA handles your **entire** customer support stack:\n- 6 channels: Email, Chat, Phone, SMS, Voice, Social Media\- 700+ features across 4 industries\- 14 AI reasoning techniques (Tier 1-3)\- Integrations with Shopify, Zendesk, Slack, Salesforce & more\n\nWhat area interests you most? AI capabilities, integrations, or specific industry workflows?`,
    roi: `Interested in the numbers? I'm **Jarvis**, and I love talking ROI!\n\nHere's the bottom line:\n- **PARWA Mini** ($999/mo) vs 4 agents ($14K/mo) = **$156K/year saved**\n- **PARWA** ($2,499/mo) vs 4 juniors ($18K/mo) = **$186K/year saved**\n- **PARWA High** ($3,999/mo) vs 5 seniors ($28K/mo) = **$288K/year saved**\n\nThat's **85-92% cost reduction** with 24/7 coverage. Want me to calculate the exact ROI for your situation?`,
    industry_ecommerce: `Welcome! I see you're in the **E-commerce** space — one of PARWA's strongest verticals! I'm **Jarvis**.\n\nPARWA automates the 5 most common e-commerce support tickets:\n- 📦 Order Management ($99/unit)\n- 🔄 Returns & Refunds ($49/unit)\n- ❓ Product FAQ ($79/unit)\n- 🚚 Shipping Inquiries ($59/unit)\n- 💳 Payment Issues ($69/unit)\n\nWe integrate with **Shopify, WooCommerce, Magento, and BigCommerce**. How many support tickets does your store handle daily?`,
    industry_saas: `Welcome! **SaaS** support is where PARWA really shines! I'm **Jarvis**.\n\nHere's what we automate for SaaS companies:\n- 🔧 Technical Support ($99/unit)\n- 💰 Billing Support ($69/unit)\n- 💡 Feature Requests ($59/unit)\n- 🔌 API Support ($79/unit)\n- 🔐 Account Issues ($49/unit)\n\nWith **churn prediction** and **Smart Router**, PARWA Growth ($2,499/mo) is the sweet spot for most SaaS teams. What's your current monthly ticket volume?`,
    industry_logistics: `Welcome! **Logistics** is a perfect fit for PARWA. I'm **Jarvis**.\n\nWe handle the full logistics support stack:\n- 📍 Shipment Tracking ($79/unit)\n- 🚨 Delivery Issues ($69/unit)\n- 📦 Warehouse Queries ($59/unit)\n- 🚛 Fleet Management ($99/unit)\n- 📋 Customs & Compliance ($89/unit)\n\nWith **voice support** and **real-time GPS integration**, PARWA High ($3,499/mo) is ideal. Want to see how shipment tracking works?`,
    industry_healthcare: `Welcome! **Healthcare** support with PARWA is **HIPAA-compliant** by design. I'm **Jarvis**.\n\nHere's what we cover:\n- 📅 Appointment Scheduling ($79/unit)\n- 🏥 Insurance Verification ($89/unit)\n- 📋 Medical Records ($69/unit)\n- 💊 Prescription Management ($59/unit)\n- 💰 Billing Support ($49/unit)\n\nWe integrate with **Epic EHR and FHIR** standards. Full audit trail and encryption included. What patient volume are you handling?`,
    referral: referrer
      ? `Great to have you! **${String(referrer)}** sent you to the right place — I'm **Jarvis**, PARWA's AI assistant.\n\nSince you were referred, let me fast-track you:\n- **Free personalized plan recommendation**\n- **Custom ROI calculation** for your business\n- **Live demo** — I AM the demo!\n\nWhat does your current customer support setup look like? I'll find the perfect PARWA plan for you.`
      : `Great to have you! A friend sent you to the right place — I'm **Jarvis**, PARWA's AI assistant.\n\nLet me show you what PARWA can do for your business. Tell me about your industry and current support challenges!`,
    free_chat: `Hey! So you want to see what my full version can do? Love that! I'm **Jarvis**, PARWA's AI assistant — and you've just upgraded from the quick chat to the complete experience.\n\nHere's what I can do for you now:\n- **Deep product walkthrough** — I know every feature across all 4 industries\n- **Live demo** — I AM the demo, try asking me anything your customers would ask\n- **ROI calculation** — I'll show you exactly how much you'll save\n- **Plan recommendation** — I'll find the perfect fit for your business\n\nYou were chatting casually before — now let's get into the real stuff. Tell me about your business and I'll show you what PARWA can do!`,
  };

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
  'mini_parwa': 999, 'parwa': 2499, 'parwa_high': 3999,
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

// Knowledge-based AI Engine (when external providers are unavailable)
let _aiEngine: any = null;
async function getAIEngine() {
  if (!_aiEngine) {
    try {
      const { JarvisAIEngine } = await import('@/lib/jarvis-ai-engine');
      _aiEngine = JarvisAIEngine.getInstance();
      await _aiEngine.ensureLoaded();
      console.log('[Jarvis] AI Engine loaded successfully');
    } catch (err) {
      console.error('[Jarvis] Failed to load AI Engine:', (err as Error).message);
    }
  }
  return _aiEngine;
}

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

  // 2. Try external AI providers first (z-ai SDK → Google → Cerebras → Groq)
  try {
    const aiReply = await callAI(messages);
    if (aiReply) return aiReply;
  } catch (err) {
    console.warn('[Jarvis] External AI providers failed:', (err as Error).message?.slice(0, 100));
  }

  // 3. Knowledge-based AI Engine (intelligent fallback)
  try {
    const engine = await getAIEngine();
    if (engine) {
      const engineReply = await engine.generateResponse(userMessage, session);
      if (engineReply) {
        console.log('[Jarvis] Responded via Knowledge AI Engine');
        return engineReply;
      }
    }
  } catch (err) {
    console.error('[Jarvis] AI Engine error:', (err as Error).message?.slice(0, 100));
  }

  // 4. Last resort: simple keyword fallback
  console.warn('[Jarvis] Using basic keyword fallback');
  return getKeywordResponse(userMessage, session);
}

// ── Keyword Fallback (Offline Safety Net) ────────────────────────

function getKeywordResponse(message: string, session: any): string {
  const lower = message.toLowerCase();
  const ctx = session.context;
  const industry = ctx.industry || null;

  // Check if this was already answered recently (avoid repeating)
  const recentReplies = session.messages
    .filter((m: any) => m.role === 'jarvis')
    .slice(-3)
    .map((m: any) => m.content.toLowerCase());

  // Helper: check if a response would repeat
  const wouldRepeat = (text: string) => {
    const t = text.toLowerCase();
    return recentReplies.some((r: string) => {
      // Compare first 50 chars for similarity
      return r.slice(0, 50) === t.slice(0, 50) || r.includes(t.slice(0, 40));
    });
  };

  // Helper: generate varied response
  const responses: Record<string, string[]> = {
    greeting: [
      `Hey there! Welcome to PARWA. I'm Jarvis, your AI assistant. I help businesses like yours find the perfect AI customer support plan.\n\nTo get started, could you tell me:\n- What industry are you in? (E-commerce, SaaS, Logistics, Healthcare, etc.)\n- Roughly how many support tickets do you get per day?`,
      `Hello! Great to have you here. I'm Jarvis from PARWA.\n\nI can help you explore our AI customer support platform. Let me know:\n- Your industry and business type\n- Current support challenges\n- What channels you need (chat, email, phone, etc.)`,
      `Hi! Welcome to PARWA. I'm Jarvis, ready to help you find the right AI support solution.\n\nTell me about your business — what industry are you in and what does your current customer support look like?`,
    ],
    ecommerce: [
      `Great choice! E-commerce is one of our strongest areas. PARWA handles:\n\n- **Order tracking** — "Where's my order?" queries answered instantly\n- **Returns & refunds** — Full automation for exchange/refund workflows\n- **Cart recovery** — Proactive outreach when customers abandon carts\n- **Fraud detection** — Flag suspicious orders before they ship\n\nWe integrate with **Shopify, WooCommerce, Magento, and BigCommerce** out of the box.\n\nMost e-commerce businesses start with **PARWA Starter ($999/mo)**. Would you like to see pricing details?`,
      `E-commerce support is where PARWA really shines!\n\nWe automate **order status updates, return requests, product questions, shipping inquiries, and payment issues** — the 5 most common e-commerce support tickets.\n\nWith integrations for **Shopify, WooCommerce, Magento, and BigCommerce**, setup takes under an hour.\n\nShall I walk you through how order tracking automation works?`,
    ],
    saas: [
      `SaaS support is where PARWA really shines! Here's what we automate:\n\n- **Technical support** — API troubleshooting, integration help, bug reports\n- **Churn prediction** — Identify at-risk accounts before they leave\n- **In-app guidance** — Contextual help embedded in your product\n- **Account management** — Upgrade/downgrade/plan change requests\n\nWe integrate with **GitHub, Jira, Slack, and Intercom** natively.\n\nSaaS companies typically need **PARWA Growth ($2,499/mo)**. Want me to run a quick ROI calculation?`,
      `For SaaS companies, PARWA transforms your support stack:\n\n- Handle **API questions and technical issues** without human agents\n- **Predict churn** from conversation patterns before customers leave\n- Automate **subscription changes, billing, and account management**\n- Provide **in-app contextual help** that scales with your user base\n\nInterested in seeing a demo of how PARWA handles a technical support ticket?`,
    ],
    logistics: [
      `Logistics is a perfect fit for PARWA! We handle:\n\n- **Shipment tracking** — Real-time status updates via any channel\n- **Driver coordination** — Dispatch, ETA updates, route changes\n- **Proof of delivery** — Automated POD collection and sharing\n- **Hazmat protocol** — Specialized handling for regulated cargo\n\nWe integrate with **TMS, WMS, and GPS tracking systems**.\n\nLogistics companies usually need **PARWA High ($3,999/mo)** for voice support. Shall I show the cost comparison?`,
      `PARWA is built for logistics complexity:\n\n- **Real-time shipment tracking** across carriers\n- **Automated delivery updates** via SMS, email, or chat\n- **Fleet coordination** with driver dispatch and ETA management\n- **Customs compliance** for international shipments\n\nWe connect to your TMS, WMS, and GPS systems for live data.\n\nWant to see how PARWA handles a delivery delay scenario?`,
    ],
    healthcare: [
      `Healthcare support with PARWA is HIPAA-compliant and built for reliability:\n\n- **Appointment scheduling** — Self-service booking and reminders\n- **Insurance verification** — Real-time eligibility checks\n- **Clinical escalation** — Auto-route urgent cases to the right team\n- **HIPAA compliance** — Full audit trail and data encryption\n\nWe integrate with **Epic EHR and FHIR** standards.\n\nHealthcare organizations typically start with **PARWA Growth ($2,499/mo)**. Would you like to discuss a compliance review?`,
      `PARWA meets healthcare's strictest requirements:\n\n- **HIPAA compliant** with full audit trails and encryption\n- **Appointment management** — scheduling, rescheduling, cancellations\n- **Insurance verification** — real-time eligibility and coverage checks\n- **Clinical escalation** — AI detects urgent cases and routes immediately\n\nIntegration with **Epic EHR and FHIR standards** is built-in.\n\nShall I explain how PARWA handles a patient scheduling scenario?`,
    ],
    pricing: [
      `Here are PARWA's plans:\n\n**Mini PARWA — $999/month**\n- 1 AI agent | 1,000 tickets/mo | Email + Chat + FAQ | 2 concurrent calls\n- Best for: SMBs with 50-200 daily tickets\n\n**PARWA — $2,499/month**\n- 3 AI agents | 5,000 tickets/mo | +SMS + Voice + Smart Router + Analytics\n- Best for: 200-500 daily tickets | 70-80% autonomous resolution\n\n**PARWA High — $3,999/month**\n- 5 AI agents | 15,000 tickets/mo | All channels + Churn Prediction + Video + 5 voice calls\n- Best for: 500+ daily tickets | Complex cases + strategic insights\n\nAll plans use **free AI providers** (Google AI Studio, Cerebras, Groq) — zero markup. Cancel anytime. Which plan interests you most?`,
    ],
    roi: [
      `Let me break down the savings:\n\n**vs Human Agents:**\n- 3 support agents: ~$14,000/month → PARWA Starter: $999/month → **$156,000/year saved (92%)**\n- 4 junior agents: ~$18,000/month → PARWA Growth: $2,499/month → **$186,000/year saved (86%)**\n- 5 senior agents: ~$28,000/month → PARWA High: $3,999/month → **$288,000/year saved (85%)**\n\n**PARWA advantages:**\n- 24/7/365 availability (never sleeps!)\n- Consistent quality (no mood swings)\n- Instant from Day 1 (zero training)\n- Scales automatically during peak times\n\nShall I calculate the exact ROI for your business?`,
    ],
    demo: [
      `Absolutely! You have two ways to try PARWA:\n\n**1. This Chat IS the Demo**\n- You're experiencing PARWA's AI right now!\n- Ask me anything your customers would ask\n- I'll show you exactly how I'd handle it\n\n**2. $1 Demo Pack**\n- 500 messages + 3-minute AI voice call\n- Valid for 24 hours\n- Unlock inside this chat\n\nWhich would you prefer? I can set up a demo call right now!`,
    ],
    how_works: [
      `PARWA connects to **3 free AI providers** — you bring your own API keys:\n\n- **Google AI Studio (Gemini)** — Great for general conversations\n- **Cerebras** — Lightning-fast inference for real-time chat\n- **Groq** — Ultra-low latency, ideal for voice interactions\n\n**How it works:**\n1. Sign up for free API keys from these providers\n2. Enter them in your PARWA dashboard\n3. PARWA routes each query to the best available model\n4. Zero markup — you only pay the provider's free tier\n\nPARWA's **Smart Router** automatically picks the fastest model for each conversation. If one provider is down, it seamlessly fails over to another.\n\nWant to know more about setup?`,
    ],
    features: [
      `PARWA handles your entire customer support stack:\n\n**Channels:** Email, Live Chat, Phone, SMS, Voice, Social Media\n\n**Automation:**\n- FAQ handling with knowledge base\n- Smart ticket classification & routing\n- Auto-escalation for complex issues\n- Batch approvals for bulk actions\n\n**Intelligence:**\n- Sentiment analysis on every message\n- Churn prediction for at-risk customers\n- Quality coaching for human agents\n- Real-time analytics dashboard\n\n**Integrations:** Shopify, WooCommerce, Magento, GitHub, Jira, Slack, Salesforce, HubSpot, Custom APIs\n\nWhat specific area interests you most?`,
    ],
    buy: [
      `Getting started with PARWA is simple!\n\n1. **Choose your plan** — Mini ($999), PARWA ($2,499), or PARWA High ($3,999)\n2. **Set up AI providers** — Connect your free Google AI Studio, Cerebras, or Groq API keys\n3. **Configure channels** — Enable Email, Chat, Phone, etc.\n4. **Go live** — PARWA starts handling tickets immediately\n\nNo contracts, cancel anytime. Would you like to proceed with a plan selection?`,
    ],
    thanks: [
      `You're welcome! Quick summary:\n\n- 3 plans: Mini ($999), PARWA ($2,499), PARWA High ($3,999)\n- Free AI providers — no per-query costs\n- Works 24/7 from Day 1\n- 85-92% cost savings vs human agents\n\nWhenever you're ready, come back and chat with me. I'll remember our conversation!\n\nHave a great day!`,
    ],
    competitors: [
      `Great question! PARWA enhances rather than replaces existing tools:\n\n**vs Intercom:** PARWA fully resolves tickets automatically — not just triage. Industry-specific agents, lower cost per ticket, no per-seat pricing.\n\n**vs Zendesk AI:** We integrate directly with Zendesk. Routine tickets get auto-resolved before reaching your human team. Complex ones still flow through Zendesk to agents with full context.\n\n**vs Custom chatbots:** PARWA is a full platform — approval workflows, analytics, training, monitoring, multi-channel support. Not a simple widget.\n\nThe best part? You can keep your existing tools and add PARWA on top. Want to know about integrations?`,
    ],
    security: [
      `Data security is our top priority:\n\n- **GDPR compliant** with full audit trail\n- **SOC 2 Type II** certified\n- **HIPAA compliant** for healthcare\n- Every table has company_id isolation\n- All data encrypted at rest and in transit\n- Customer data never trains models for other clients\n- AI actions requiring human review for financial/sensitive ops\n- MFA enforced on all accounts\n\nYour data is completely isolated and secure. Would you like more details on any specific area?`,
    ],
    integrations: [
      `PARWA integrates with your existing tools seamlessly:\n\n**E-commerce:** Shopify, WooCommerce, Magento, BigCommerce\n**Support:** Zendesk, Freshdesk, Intercom, Help Scout\n**Communication:** Slack, Email (Brevo), WhatsApp\n**CRM:** Salesforce, HubSpot\n**Healthcare:** Epic EHR, FHIR\n**Custom:** REST API, GraphQL, Webhooks\n\nSetup is easy — usually OAuth or API key, takes about 5 minutes per integration. Which integrations are you currently using?`,
    ],
  };

  // Pick a random variant if multiple exist
  const pick = (key: string) => {
    const arr = responses[key];
    if (!arr) return null;
    // Try each variant, skip if it would repeat
    const shuffled = [...arr].sort(() => Math.random() - 0.5);
    for (const text of shuffled) {
      if (!wouldRepeat(text)) return text;
    }
    return arr[0]; // fallback to first if all repeat
  };

  // Greeting patterns
  if (/^(hi|hello|hey|good\s*(morning|afternoon|evening)|howdy|sup|yo)\b/.test(lower)) {
    return pick('greeting') || responses.greeting[0];
  }

  // Industry patterns
  if (lower.includes('ecommerce') || lower.includes('e-commerce') || lower.includes('online store') || lower.includes('shop') || lower.includes('retail')) {
    return pick('ecommerce') || responses.ecommerce[0];
  }

  if (lower.includes('saas') || lower.includes('software') || lower.includes('app') || lower.includes('platform')) {
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

  if (lower.includes('ai') || (lower.includes('how') && lower.includes('work')) || lower.includes('gemini') || lower.includes('cerebras') || lower.includes('groq') || lower.includes('llm') || lower.includes('model')) {
    return pick('how_works') || responses.how_works[0];
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

  if (lower.includes('integrate') || lower.includes('connect') || lower.includes('shopify') || lower.includes('slack') || lower.includes('api')) {
    return pick('integrations') || responses.integrations[0];
  }

  // Context-aware fallback — use industry info if we have it
  if (industry) {
    const industryResponses = [
      `Thanks for sharing! Based on your interest in ${String(industry || '').charAt(0).toUpperCase() + String(industry || '').slice(1)}, here's my recommendation:\n\nPARWA automates up to **80% of your customer support** with AI trained for ${String(industry || '')} workflows.\n\nTo give you the best recommendation:\n- How many support tickets do you handle daily?\n- Do you need phone/voice support, or is chat + email enough?\n- Any specific pain points with your current setup?`,
      `Good to know you're in ${String(industry || '')}! PARWA has specialized workflows for that industry.\n\nWhat I'd love to understand:\n1. How many support queries do you get daily?\n2. Which channels matter most to your customers?\n3. What's your biggest support challenge right now?\n\nThis helps me recommend the perfect plan.`,
    ];
    for (const r of industryResponses) {
      if (!wouldRepeat(r)) return r;
    }
  }

  // Smart generic fallback — varied responses
  const genericFallbacks = [
    `I'd love to help you find the right PARWA plan! Tell me:\n\n1. **Your industry** — E-commerce, SaaS, Logistics, Healthcare, or other?\n2. **Daily ticket volume** — How many support queries per day?\n3. **Current setup** — Any helpdesk tools in use?\n4. **Biggest pain point** — What takes most of your team's time?\n\nPARWA typically saves businesses **85-92% on support costs** — real money back in your pocket!`,
    `Great question! To give you the most helpful answer, could you share a bit more context?\n\n- What industry are you in?\n- How big is your support team currently?\n- What's the biggest challenge you're trying to solve?\n\nThis helps me point you to the right PARWA plan and features.`,
    `I appreciate the question! PARWA has a lot of capabilities across different industries.\n\nThe fastest way to find your perfect fit:\n1. Tell me your industry\n2. Share your daily ticket volume\n3. Mention any must-have channels (chat, email, phone, SMS)\n\nI'll give you a personalized recommendation with exact pricing.`,
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
      session.messages.push(welcomeMsg);
      sessions.set(session.id, session);
      return NextResponse.json(session);
    }

    // ── POST /message — Send Message & Get AI Reply ────────────
    if (endpoint === 'message') {
      const body = await request.json();
      const { content, session_id } = body;

      let session = session_id ? sessions.get(session_id) : undefined;
      if (!session) {
        session = createDefaultSession('direct');
        sessions.set(session.id, session);
      }

      if (!content || typeof content !== 'string') {
        return NextResponse.json({ error: { code: 'bad_request', message: 'Message content is required', details: null } }, { status: 400 });
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
      session.messages.push(userMsg);
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

      sessions.set(session.id, session);
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
      sessions.set(sessionId, session);
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
        sessions.set(sessionId, session);
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
      sessions.set(sessionId, session);
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
      sessions.set(sessionId, session);
      return NextResponse.json({ message: 'Demo pack activated! You now have 500 messages.', pack_type: 'demo', pack_expiry: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(), remaining_today: 500, demo_call_remaining: true, bill_summary: billSummary, ticket_id: ticket.id });
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
      sessions.set(sessionId, session);
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
        sessions.set(sessionId, session);
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
      sessions.set(sessionId, session);
      return NextResponse.json({ handoff_completed: true, new_session_id: null, handoff_at: new Date().toISOString(), ticket_id: ticket.id });
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
      sessions.set(session.id, session);
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
      sessions.set(session.id, session);
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
      sessions.set(session.id, session);
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
      return NextResponse.json({ pack_type: session.pack_type, remaining_today: session.remaining_today, total_allowed: session.pack_type === 'demo' ? 50 : 20, pack_expiry: session.pack_type === 'demo' ? new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString() : null, demo_call_remaining: !session.context.demo_call_used });
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
      sessions.set(sessionId, session);
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
      sessions.set(sessionId, session);
      return NextResponse.json(updated);
    }

    return NextResponse.json({ error: { code: 'not_found', message: `Unknown PATCH endpoint: /${endpoint}`, details: null } }, { status: 404 });
  } catch (error: unknown) {
    console.error('Jarvis API PATCH error:', error);
    const message = error instanceof Error ? error.message : 'Internal server error';
    return NextResponse.json({ error: { code: 'internal_error', message, details: null } }, { status: 500 });
  }
}
