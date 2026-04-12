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

// ── Free AI Providers ──────────────────────────────────────────

function getGoogleProvider(): any {
  const key = process.env.GOOGLE_AI_API_KEY;
  return {
    name: 'google',
    apiKey: key,
    model: 'gemini-3.1-flash-lite',
    apiUrl: `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key=${key}`,
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
  const key = process.env.CEREBRAS_API_KEY;
  return {
    name: 'cerebras',
    apiKey: key,
    model: 'llama3.1-8b',
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
  const key = process.env.GROQ_API_KEY;
  return {
    name: 'groq',
    apiKey: key,
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
    case 'google': return process.env.GOOGLE_AI_API_KEY ? getGoogleProvider() : null;
    case 'cerebras': return process.env.CEREBRAS_API_KEY ? getCerebrasProvider() : null;
    case 'groq': return process.env.GROQ_API_KEY ? getGroqProvider() : null;
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

  // Dynamic context
  const contextLines = [
    selectedIndustry ? `Industry: ${String(selectedIndustry)}` : '',
    ctx.referral_source ? `Referred by: ${ctx.referral_source}` : '',
    ctx.pages_visited?.length > 0 ? `Pages visited: ${ctx.pages_visited.join(', ')}` : '',
    entrySourceParam === 'models_page' && selectedVariant ? `Came from models page → selected ${selectedVariant} for live demo` : '',
    entrySourceParam === 'models_page' && !selectedVariant ? `Came from models page, was browsing plans` : '',
    entrySource === 'roi' ? `Came from ROI calculator — interested in cost savings` : '',
    ctx.concerns_raised?.length > 0 ? `Concerns raised: ${ctx.concerns_raised.join(', ')}. Address these naturally.` : '',
  ].filter(Boolean).join('\n');

  // ── Recent conversation memory ──
  const recentMsgs = session.messages.slice(-6);
  const conversationMemory = recentMsgs.map((m: any) => {
    const role = m.role === 'jarvis' ? 'Jarvis' : m.role === 'user' ? 'User' : 'System';
    return `${role}: ${String(m.content).slice(0, 120)}`;
  }).join('\n');

  return `You are Jarvis — PARWA's AI assistant. Think Iron Man's Jarvis: you know everything about the product, you're proactive, you guide, you sell by showing, you demo by doing.

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
- Bullet points for meat (2-5, emojis, blank lines between)
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
  const ep = ctx.entry_params || {};
  const variant = ep.variant || ctx.variant || null;
  const variantId = ep.variant_id || ctx.variant_id || null;
  const industry = ep.industry || ctx.industry || null;
  const entryParamSource = ep.entry_source || source;
  const ind = industry ? String(industry).toLowerCase() : null;

  // Rich context from models page
  const roi = ep.roi ? String(ep.roi) : null;
  const scenario = ep.scenario ? String(ep.scenario) : null;
  const uniqueFeatures = ep.unique_features ? String(ep.unique_features) : null;
  const integrations = ep.integrations ? String(ep.integrations) : null;

  // ── Variant + Industry specific welcome (from "Try Live Chat — Free") ──
  if (variant && (entryParamSource.includes('free_chat') || entryParamSource === 'models_page')) {
    const vName = String(variant);
    const isS = variantId === 'starter' || vName.toLowerCase().includes('starter');
    const isG = variantId === 'growth' || vName.toLowerCase().includes('growth');
    const isH = variantId === 'high' || vName.toLowerCase().includes('high');

    let featureBullets = '';
    if (uniqueFeatures) {
      const feats = uniqueFeatures.split(',').slice(0, 3);
      featureBullets = feats.map((f: string) => `• ✨ ${f.trim()}`).join('\n');
    }
    if (integrations) featureBullets += `\n• 🔗 Integrates with ${integrations}`;

    if (isS) return `Hey! 👋 You're now talking to PARWA Starter — "The 24/7 Trainee"${ind ? ` for ${industry}` : ''}.\n\nHere's what I bring to the table:\n\n• 🤖 Handle emails & chat 24/7 — no more midnight support shifts\n• 📋 Collect customer data automatically — orders, returns, FAQs\n• 📞 Take phone calls (up to 2 at once)\n${featureBullets}\n• 💰 Only $999/mo — saves you ~$168K/yr vs hiring trainees\n\nI gather info fast and escalate anything complex to your team. What do your customers ask about most? Let me show you how I'd handle it. 😊`;
    if (isG) return `Hey! 👋 You're talking to PARWA Growth — "The Junior Agent"${ind ? ` for ${industry}` : ''}.\n\nThis is where PARWA gets really smart. Here's what I do:\n\n• 🧠 Smart recommendations — I analyze tickets and suggest actions\n• 📊 Churn prediction — I detect usage drops BEFORE customers leave\n• 📞 Handle up to 3 calls simultaneously + SMS + Voice\n${featureBullets}\n• 💰 $2,499/mo — saves ~$216K/yr vs hiring junior agents\n\nI don't just answer — I think.${scenario ? `\n\nReal example: ${scenario}` : ''}\n\nWhat's your biggest support headache right now? I'll show you exactly how I'd solve it. 🚀`;
    if (isH) return `Hey! 👋 You're talking to PARWA High — "The Senior Agent"${ind ? ` for ${industry}` : ''}.\n\nFull autonomous mode. Here's what makes me different:\n\n• ✅ I approve actions up to $50 on my own — no human bottleneck\n• 🧠 Predict churn & coordinate across departments automatically\n• 📞 5 concurrent calls + video support with screen sharing\n${featureBullets}\n• 💰 $3,999/mo — saves ~$336K/yr vs hiring senior agents\n\nI don't assist — I lead.${scenario ? `\n\nReal example: ${scenario}` : ''}\n\nWhat's a complex scenario your support team struggles with? Let me handle it. 🔥`;
  }

  // ── Industry-specific welcomes ──
  if (ind && !variant) {
    const map: Record<string, string> = {
      ecommerce: `Hey! 🛒 E-commerce is one of our strongest verticals!\n\nPARWA automates the heavy lifting:\n\n• 📦 Orders, returns, tracking & FAQ — fully automated\n• 🚚 Shipping & payment issues resolved in seconds\n• 🔗 Shopify, WooCommerce, Magento, BigCommerce ready\n• 💰 Starting at $999/mo — saves ~$168K/yr\n\nHow many support tickets does your store handle daily?`,
      saas: `Hey! 💻 SaaS support — this is where PARWA really shines!\n\nHere's what we automate:\n\n• 🐛 Tech support & multi-step troubleshooting\n• 💳 Billing, subscriptions & API key management\n• 📉 Churn prediction — detect at-risk users before they leave\n• 💰 Starting at $999/mo — saves ~$168K/yr\n\nWhat's your monthly ticket volume?`,
      logistics: `Hey! 🚛 Logistics is a perfect fit for PARWA!\n\nWe handle the full operations stack:\n\n• 📍 Real-time shipment tracking via carrier APIs\n• 🚚 Delivery issues, rerouting & driver coordination\n• 🏭 Fleet & warehouse management\n• 💰 Starting at $999/mo — saves ~$168K/yr\n\nWant to see how shipment tracking automation works?`,
      others: `Hey! 👋 Whatever your industry — PARWA adapts.\n\nHere's what we bring:\n\n• 🤖 Custom workflows tailored to YOUR business\n• 🔗 20+ integrations out of the box\n• 📊 Advanced analytics & pattern recognition\n• 💰 Starting at $999/mo — save 85-92% vs hiring\n\nWhat does your current support setup look like?`,
    };
    return map[ind] || map.others;
  }

  const welcomes: Record<string, string> = {
    direct: `Hey! 👋 I'm Jarvis — PARWA's AI assistant.\n\nI can help you with a few things right now:\n\n• 🤖 Find the right plan for your business (Starter / Growth / High)\n• 💰 Calculate your exact ROI savings\n• 🎥 Run a live demo\n\nWhat's your industry and how many tickets do you handle? I'll point you to the right fit.`,
    pricing: `Hey! 👋 Checking out our plans — smart move.\n\nHere's the full lineup:\n\n• 🟠 Starter — $999/mo — 3 agents, 1K tickets — saves ~$168K/yr\n• 🟠 Growth — $2,499/mo — 8 agents, 5K tickets — saves ~$216K/yr\n• 🟠 High — $3,999/mo — 15 agents, 15K tickets — saves ~$336K/yr\n\nAll with 24/7 coverage, cancel anytime. What's your industry? I'll tell you which plan fits best.`,
    demo: `Hey! 🎉 You're in the right place — I AM the demo!\n\nTry asking me what your customers would:\n\n• "Where's my order #12345?"\n• "My API key isn't working"\n• "I need a refund for this"\n\nOr grab the $1 Demo Pack — 500 messages + a 3-minute AI voice call. Want me to set that up?`,
    features: `Hey! 👋 Exploring what PARWA can do?\n\nHere's the rundown:\n\n• 📬 6 channels — Email, Chat, Phone, SMS, Voice, Social\n• 🧠 700+ features across 4 industries\n• 🔗 20+ integrations (Shopify, Slack, Jira, Salesforce...)\n• 📊 Smart routing, churn prediction, sentiment analysis\n\nWhat area interests you most?`,
    roi: `Hey! 📊 ROI-focused — love it.\n\nHere's what PARWA actually saves:\n\n• Starter → saves ~$168K/yr (replaces $14K/mo in salaries)\n• Growth → saves ~$216K/yr (replaces $18K/mo in salaries)\n• High → saves ~$336K/yr (replaces $28K/mo in salaries)\n\nThat's 85-92% cost reduction with 24/7 coverage. Want me to calculate your exact number?`,
    referral: `Hey! 👋 Great to have you here!\n\nI can help with a few things:\n\n• 💡 Free plan recommendation based on your business\n• 📊 ROI calculation with real numbers\n• 🎥 Live demo\n\nWhat does your current support setup look like?`,
    free_chat: `Hey! 👋 Welcome to the full PARWA experience!\n\nI can do a deep product walkthrough, live demo, ROI calculation, or plan recommendation right here.\n\nTell me about your business — industry, ticket volume, biggest support pain — and I'll show you exactly what PARWA can do. 🚀`,
    models_page: `Hey! 👋 Welcome from our Models page!\n\nQuick recap of the lineup:\n\n• 🟠 Starter — $999/mo — "The 24/7 Trainee" — great for SMBs\n• 🟠 Growth — $2,499/mo — "The Junior Agent" — smart & proactive\n• 🟠 High — $3,999/mo — "The Senior Agent" — fully autonomous\n\nWant to try one out? I can roleplay as any of them right now — just tell me your industry. 😊`,
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

  // 3. Call AI with smart routing (z-ai SDK → Google → Cerebras → Groq → keyword fallback)
  const aiReply = await callAI(messages);
  if (aiReply) return aiReply;

  // 4. Keyword fallback (always works)
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
      `Hey there! 👋 Welcome to PARWA — I'm Jarvis.\n\nWhat industry are you in and how many support tickets do you handle daily? I'll find the perfect plan for you!`,
      `Hello! 👋 Great to have you. I'm Jarvis from PARWA.\n\nTell me about your business and current support setup — I'll recommend the right plan!`,
      `Hi! 👋 I'm Jarvis, ready to help.\n\nWhat's your industry and biggest support pain point right now?`,
    ],
    ecommerce: [
      `🛒 E-commerce is one of our strongest areas!\n\n- Order tracking, returns, FAQ, shipping & payments — all automated\n- Integrates with Shopify, WooCommerce, Magento & BigCommerce\n\nMost e-com stores start with PARWA Starter ($999/mo). Want pricing details?`,
      `E-commerce support is where PARWA shines! 🛍️\n\nWe automate the top 5 support tickets with Shopify/WooCommerce/Magento integration. Setup takes under an hour.\n\nWant to see how order tracking works?`,
    ],
    saas: [
      `💻 SaaS support with PARWA automates the heavy lifting!\n\n- Tech support, churn prediction, billing & API help\n- Integrates with GitHub, Jira, Slack & Intercom\n\nMost SaaS teams go with PARWA Growth ($2,499/mo). Want a quick ROI calc?`,
      `🚀 For SaaS, PARWA transforms your support stack.\n\nAPI questions, churn prediction, subscription changes & in-app help — all automated.\n\nWant to see a demo of a tech support ticket?`,
    ],
    logistics: [
      `🚛 Logistics is a perfect fit for PARWA!\n\n- Shipment tracking, driver coordination, delivery updates & customs\n- Integrates with TMS, WMS & GPS systems\n\nCompanies usually go PARWA High ($3,999/mo) for voice support. Want the cost breakdown?`,
      `📦 PARWA is built for logistics complexity.\n\nReal-time tracking, automated updates & fleet coordination — all connected to your existing systems.\n\nWant to see a delivery delay scenario?`,
    ],
    healthcare: [
      `🏥 Healthcare support with PARWA is HIPAA-compliant by design.\n\n- Appointments, insurance verification, records & clinical escalation\n- Integrates with Epic EHR & FHIR\n\nMost healthcare orgs start with PARWA Growth ($2,499/mo). Want to discuss compliance?`,
      `✅ PARWA meets healthcare's strictest requirements.\n\nHIPAA compliant, full audit trails, encryption & smart clinical escalation built in.\n\nWant to see a patient scheduling scenario?`,
    ],
    pricing: [
      `💰 Here's the lineup:\n\n• 🟠 PARWA Starter — $999/mo — 1 agent, 1K tickets/mo\n• 🟠 PARWA Growth — $2,499/mo — 3 agents, 5K tickets/mo\n• 🟠 PARWA High — $3,999/mo — 5 agents, 15K tickets/mo\n\nAll with zero AI markup, cancel anytime. Which one fits your needs?`,
    ],
    roi: [
      `📊 Here's the math:\n\n• PARWA Starter → saves ~$156K/yr (vs 3 agents)\n• PARWA Growth → saves ~$186K/yr (vs 4 juniors)\n• PARWA High → saves ~$288K/yr (vs 5 seniors)\n\nThat's 85-92% savings with 24/7 coverage. Want me to calculate yours?`,
      `💡 Bottom line: PARWA saves 85-92% vs hiring agents.\n\nPlus 24/7 coverage, zero training time & instant scaling during peaks.\n\nWant the exact number for your business?`,
    ],
    demo: [
      `🎉 You're in luck — this chat IS the demo!\n\nAsk me anything your customers would ask. Or grab a $1 Demo Pack for 500 messages + an AI voice call.\n\nWant me to set that up?`,
      `✨ Try me right now — I AM the demo!\n\nAsk something like "Where's my order?" and I'll show you how PARWA handles it.\n\nOr get the $1 Demo Pack for the full experience!`,
    ],
    how_works: [
      `🤖 PARWA uses cutting-edge AI fine-tuned for customer support.\n\n- Bring your own AI keys — zero markup on AI costs\n- Smart routing picks the best model for each conversation\n- Works across email, chat, phone, SMS & voice\n\nWant to know about setup?`,
      `⚙️ PARWA connects to your tools and starts handling tickets on Day 1.\n\nBring your own AI keys (zero markup), configure your channels, and go live.\n\nWant to hear about the setup process?`,
    ],
    features: [
      `🎯 PARWA covers your entire support stack:\n\n- 📬 6 channels — Email, Chat, Phone, SMS, Voice, Social\n- 🧠 Smart routing, sentiment analysis, churn prediction\n- 🔗 20+ integrations out of the box\n\nWhat area interests you most?`,
      `✅ PARWA's got 700+ features across 4 industries.\n\nAutomation, analytics, escalation workflows & quality coaching — all built in.\n\nWhat are you most curious about?`,
    ],
    buy: [
      `🚀 Getting started is easy:\n\n1. Pick your plan (Starter, Growth, or High)\n2. Connect your AI keys\n3. Configure your channels\n4. Go live — PARWA starts immediately\n\nNo contracts, cancel anytime. Want to pick a plan?`,
      `✨ Ready to get started?\n\nChoose your plan, connect your AI keys, and PARWA handles the rest. Takes under an hour to go live.\n\nWhich plan are you leaning toward?`,
    ],
    thanks: [
      `You're welcome! 🙌 Quick recap:\n\n• 3 plans: Starter ($999), Growth ($2,499), High ($3,999)\n• Zero AI markup, 24/7 from Day 1\n• 85-92% cost savings\n\nCome back anytime! Have a great day! 😊`,
      `Anytime! 😊 When you're ready, I'm here to help.\n\nJust come back and we'll pick up right where we left off. Have an awesome day!`,
    ],
    competitors: [
      `🥊 PARWA vs the rest:\n\n- vs Intercom: fully resolves tickets, not just triage\n- vs Zendesk AI: auto-resolves before reaching your team\n- vs Custom bots: full platform, not a widget\n\nBest part? You can keep your existing tools and add PARWA on top. Want more details?`,
      `💪 PARWA works WITH your tools, not against them.\n\nWe integrate with Zendesk, Intercom, Freshdesk & more — and auto-resolve tickets before humans see them.\n\nWant to hear about integrations?`,
    ],
    security: [
      `🔒 Security is baked in:\n\n- GDPR, SOC 2, HIPAA compliant\n- AES-256 encryption, TLS 1.3\n- Full audit trail & PII redaction\n- Your data never trains other clients' models\n\nWant more details on any area?`,
      `🛡️ Your data is safe with PARWA.\n\nGDPR + SOC 2 + HIPAA certified, encrypted at rest & in transit, with full isolation between clients.\n\nAny specific compliance question?`,
    ],
    integrations: [
      `🔗 PARWA plugs into your existing stack:\n\n- E-commerce: Shopify, WooCommerce, Magento\n- Support: Zendesk, Intercom, Freshdesk\n- Comms: Slack, WhatsApp, Email\n- CRM: Salesforce, HubSpot\n\n~5 minutes per integration. Which tools are you using?`,
      `✅ We integrate with 20+ tools out of the box.\n\nOAuth or API key setup, usually under 5 minutes each. Custom APIs & webhooks also supported.\n\nWhich integrations matter most to you?`,
    ],
    models_variants: [
      `🤖 PARWA offers 3 plans tailored to different needs:\n\n• 🟠 PARWA Starter — $999/mo (SMBs, "The Trainee")\n• 🟠 PARWA Growth — $2,499/mo (growth teams, "The Junior Agent")\n• 🟠 PARWA High — $3,999/mo (enterprise, "The Senior Agent")\n\nEach scales with your business. Which sounds like the right fit?`,
      `✨ PARWA comes in 3 tiers — Starter, Growth & High.\n\n• Different agents, ticket volumes & channel support\n• All use cutting-edge AI with zero markup\n\nWant me to recommend one based on your business?`,
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

  // Model/variant questions — redirect to 3 plans, never reveal internals
  if (lower.includes('model') || lower.includes('variant') || lower.includes('how many') || (lower.includes('which') && (lower.includes('plan') || lower.includes('option')))) {
    return pick('models_variants') || responses.models_variants[0];
  }

  if (lower.includes('ai') || (lower.includes('how') && lower.includes('work')) || lower.includes('gemini') || lower.includes('cerebras') || lower.includes('groq') || lower.includes('llm')) {
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
    const indName = String(industry || '').charAt(0).toUpperCase() + String(industry || '').slice(1);
    const industryResponses = [
      `Great choice — ${indName} is one of our specialties! 🎯\n\nPARWA automates up to 80% of support with AI trained for ${indName} workflows.\n\nHow many tickets do you handle daily? That helps me pick the right plan.`,
      `Nice! ${indName} is a great fit for PARWA. 🚀\n\nWhat's your daily ticket volume and which channels matter most? I'll find the perfect plan.`,
    ];
    for (const r of industryResponses) {
      if (!wouldRepeat(r)) return r;
    }
  }

  // Smart generic fallback — varied responses
  const genericFallbacks = [
    `Good question! 🤔 To point you the right way — what industry are you in and how many tickets do you handle daily?`,
    `I'd love to help! 💬 Tell me about your business — industry, ticket volume, and biggest support challenge?`,
    `Let's find your perfect fit! 🎯 What industry are you in and what channels do your customers use most?`,
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
