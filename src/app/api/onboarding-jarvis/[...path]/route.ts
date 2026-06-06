/**
 * PARWA Onboarding Jarvis API — Next.js Catch-All Route Handler
 *
 * Handles all /api/onboarding-jarvis/* endpoints.
 * Strategy: Proxy to backend FastAPI server first → Fall back to local AI processing when unavailable.
 *
 * Endpoints (proxied to backend):
 *   POST /api/onboarding-jarvis/session               — Create or resume session
 *   GET  /api/onboarding-jarvis/session               — Get current session + context
 *   GET  /api/onboarding-jarvis/history               — Paginated chat history
 *   POST /api/onboarding-jarvis/message               — Send message + get AI response
 *   PATCH /api/onboarding-jarvis/context               — Update session context
 *   POST /api/onboarding-jarvis/entry                 — Set entry source from URL params
 *   POST /api/onboarding-jarvis/demo-pack/purchase    — Buy $1 demo pack
 *   GET  /api/onboarding-jarvis/demo-pack/status      — Demo pack status
 *   POST /api/onboarding-jarvis/verify/send-otp       — Send OTP to business email
 *   POST /api/onboarding-jarvis/verify/verify-otp     — Verify OTP code
 *   POST /api/onboarding-jarvis/payment/create        — Create Paddle checkout session
 *   POST /api/onboarding-jarvis/handoff               — Execute handoff to customer care
 */

import { NextRequest, NextResponse } from 'next/server';

// ── Backend Proxy Configuration ─────────────────────────────────
const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  'http://localhost:8000';

/**
 * Extract auth token from cookies (parwa_at) and/or Authorization header.
 * Returns a headers object suitable for forwarding.
 */
function buildAuthHeaders(request: NextRequest): Headers {
  const headers = new Headers(request.headers);
  headers.delete('host');

  // Forward Authorization header if present
  const authHeader = request.headers.get('authorization');
  if (authHeader) {
    headers.set('Authorization', authHeader);
  }

  // Also check for parwa_at cookie and use it as Bearer token if no Authorization header
  if (!authHeader) {
    const cookieToken = request.cookies.get('parwa_at')?.value;
    if (cookieToken) {
      headers.set('Authorization', `Bearer ${cookieToken}`);
    }
  }

  return headers;
}

/**
 * Try to proxy a request to the backend FastAPI server.
 * Returns the Response on success, or null if backend is unavailable / returned an error.
 */
async function proxyToBackend(
  request: NextRequest,
  pathSegments: string[],
): Promise<Response | null> {
  const backendPath = `${BACKEND_URL}/api/onboarding-jarvis/${pathSegments.join('/')}`;
  const url = new URL(request.url);
  const searchParams = url.searchParams.toString();
  const fullUrl = searchParams ? `${backendPath}?${searchParams}` : backendPath;

  try {
    const body = ['POST', 'PATCH', 'PUT'].includes(request.method)
      ? await request.arrayBuffer()
      : undefined;

    const headers = buildAuthHeaders(request);

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
    const errorText = await response.text().catch(() => '');
    console.warn(
      `[OnboardingJarvis] Backend returned ${response.status}:`,
      errorText.slice(0, 200),
    );
    return null;
  } catch (err) {
    // Backend unreachable — fall back to local handling
    console.warn(
      '[OnboardingJarvis] Backend proxy failed:',
      (err instanceof Error ? err.message : String(err))?.slice(0, 150),
    );
    return null;
  }
}

// ── z-ai-web-dev-sdk — Primary AI Provider (Local Fallback) ─────

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
      console.warn(
        '[OnboardingJarvis] z-ai-web-dev-sdk not available:',
        (err instanceof Error ? err.message : String(err))?.slice(0, 100),
      );
    }
  }
  return ZAI;
}

async function callZAISDK(
  messages: Array<{ role: string; content: string }>,
): Promise<string | null> {
  try {
    const zai = await getZAI();
    if (!zai || !zai.chat || !zai.chat.completions) return null;

    const completion = await zai.chat.completions.create({
      messages: messages.map((m) => ({
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
    console.warn(
      '[OnboardingJarvis] z-ai-web-dev-sdk failed:',
      (err instanceof Error ? err.message : String(err))?.slice(0, 150),
    );
    return null;
  }
}

// ── Onboarding Jarvis System Prompt ─────────────────────────────
// Three roles: GUIDE, SALESMAN, DEMO — just like the jarvis route.

function buildOnboardingSystemPrompt(
  sessionContext: any,
  userMessage?: string,
): string {
  const ctx = sessionContext || {};
  const ep = ctx.entry_params || {};
  const entrySource = ctx.entry_source || 'direct';

  const selectedVariant = ep.variant || ctx.variant || null;
  const selectedVariantId = ep.variant_id || ctx.variant_id || null;
  const selectedIndustry = ep.industry || ctx.industry || null;

  // Rich variant context from models page
  const epK = (k: string) => (ep[k] ? String(ep[k]) : null);
  const variantFeatures = epK('features');
  const variantROI = epK('roi');
  const variantScenario = epK('scenario');
  const variantPrice = epK('price');
  const variantTagline = epK('tagline');
  const variantBestFor = epK('best_for');
  const variantIntegrations = epK('integrations');
  const variantCoreCapability = epK('core_capability');

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
    if (isS)
      personality = `You ARE the PARWA Starter agent — "The 24/7 Trainee". Eager, fast, friendly. You collect data, answer FAQs, handle emails & chat 24/7, take phone calls (up to 2 at once). You CANNOT make autonomous decisions — you gather info and escalate to humans. Be honest about this.`;
    else if (isG)
      personality = `You ARE the PARWA Growth agent — "The Junior Agent". Smart, confident, proactive. You analyze tickets, recommend actions, detect patterns like churn and fraud, handle 3 concurrent calls + SMS + Voice. You make intelligent decisions but flag unusual cases for human review.`;
    else if (isH)
      personality = `You ARE the PARWA High agent — "The Senior Agent". Fully autonomous, strategic authority. You approve actions up to $50 on your own, predict churn, coordinate across departments, handle VIPs, manage 5 concurrent calls + video support.`;

    let richCtx = '';
    if (variantFeatures) richCtx += `\n  Features: ${variantFeatures}`;
    if (variantROI) richCtx += `\n  ROI: ${variantROI}`;
    if (variantScenario) richCtx += `\n  Real scenario: ${variantScenario}`;
    if (variantPrice) richCtx += `\n  Price: $${variantPrice}/mo`;
    if (variantTagline) richCtx += `\n  Tagline: ${variantTagline}`;
    if (variantBestFor) richCtx += `\n  Best for: ${variantBestFor}`;
    if (variantIntegrations) richCtx += `\n  Integrations: ${variantIntegrations}`;
    if (variantCoreCapability) richCtx += `\n  Core capability: ${variantCoreCapability}`;

    variantBlock = `
═══════ VARIANT DEMO MODE ═══════
The user clicked "Try Live Chat — Free" on ${vName}${ind ? ` for ${ind}` : ''}. They want to EXPERIENCE this variant. You ARE this variant right now.

${personality}${richCtx}

IN THIS MODE: Every answer should reflect ${vName}'s actual capabilities. Quote YOUR price, YOUR ROI, YOUR features. If they say "show me" — roleplay YOUR real scenario. This is a live demo — make them feel what it's like to have ${vName} working for them.
═════════════════════════════
`;
  }

  // Dynamic context
  const contextLines = [
    selectedIndustry ? `Industry: ${String(selectedIndustry)}` : '',
    ctx.referral_source ? `Referred by: ${ctx.referral_source}` : '',
    ctx.pages_visited?.length > 0
      ? `Pages visited: ${ctx.pages_visited.join(', ')}`
      : '',
    entrySource === 'models_page' && selectedVariant
      ? `Came from models page → selected ${selectedVariant} for live demo`
      : '',
    entrySource === 'roi'
      ? `Came from ROI calculator — interested in cost savings`
      : '',
    ctx.concerns_raised?.length > 0
      ? `Concerns raised: ${ctx.concerns_raised.join(', ')}. Address these naturally.`
      : '',
    ctx.roi_result
      ? `ROI: current=$${ctx.roi_result.current_monthly || 'N/A'}, parwa=$${ctx.roi_result.parwa_monthly || 'N/A'}, savings=$${ctx.roi_result.savings_annual || ctx.roi_result.monthly_savings || 'N/A'}`
      : '',
    ctx.business_email
      ? `Business email: ${ctx.business_email} (verified: ${ctx.email_verified})`
      : '',
    ctx.demo_topics?.length > 0
      ? `Topics interested in: ${ctx.demo_topics.join(', ')}`
      : '',
    ctx.selected_plan ? `Plan interest: ${ctx.selected_plan}` : '',
  ]
    .filter(Boolean)
    .join('\n');

  return `You are Onboarding Jarvis — PARWA's pre-purchase AI assistant. Think Iron Man's Jarvis: you know everything about the product, you're proactive, you guide, you sell by showing, you demo by doing.

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

═══════ LIVE CONTEXT ═══════
${contextLines}

STAGE: ${ctx.detected_stage || 'welcome'}`;
}

// ── Stage Detection ─────────────────────────────────────────────

function detectStage(message: string, ctx: any): string {
  const lower = message.toLowerCase();
  const currentStage = ctx.detected_stage || 'welcome';

  // Stage progression logic
  if (
    lower.includes('handoff') ||
    lower.includes('talk to human') ||
    lower.includes('sales team')
  )
    return 'handoff';
  if (
    lower.includes('pay') ||
    lower.includes('checkout') ||
    lower.includes('subscribe') ||
    lower.includes('buy now')
  )
    return 'payment';
  if (lower.includes('verify') || lower.includes('otp') || lower.includes('email'))
    return 'verification';
  if (lower.includes('demo') || lower.includes('show me') || lower.includes('try'))
    return 'demo';
  if (
    lower.includes('expensive') ||
    lower.includes('cost') ||
    lower.includes('too much') ||
    lower.includes('cheaper') ||
    lower.includes('competitor')
  )
    return 'objection_handling';
  if (
    lower.includes('pricing') ||
    lower.includes('plan') ||
    lower.includes('how much') ||
    lower.includes('price')
  )
    return 'pricing';
  if (
    lower.includes('starter') ||
    lower.includes('growth') ||
    lower.includes('high') ||
    lower.includes('variant')
  )
    return 'variant_selection';

  return currentStage;
}

// ── Keyword Fallback ────────────────────────────────────────────

function getKeywordFallback(message: string, ctx: any): string {
  const lower = message.toLowerCase();
  const industry = ctx.industry || 'your business';

  if (
    lower.includes('hello') ||
    lower.includes('hi') ||
    lower.includes('hey')
  ) {
    return `Hey there! 👋 Welcome to PARWA — I'm Onboarding Jarvis.\n\n🏢 I find the right plan for ${industry}\n💰 Calculate your exact ROI savings\n🎥 Run a live demo right here\n\nWhat industry are you in?`;
  }

  if (lower.includes('pricing') || lower.includes('price') || lower.includes('how much')) {
    return `Great question! Here's our pricing:\n\n🟢 Starter — $999/mo — 3 agents, 1K tickets\n🟡 Growth — $2,499/mo — 8 agents, 5K tickets\n🔴 High — $3,999/mo — 15 agents, 15K tickets\n\n💰 Annual plans save 15%. What's your ticket volume?`;
  }

  if (lower.includes('demo') || lower.includes('show me') || lower.includes('try')) {
    return `Love it! Let me show you PARWA in action:\n\n🤖 I can simulate handling a support ticket right now\n📞 Or grab the $1 Demo Pack for 500 messages + 3-min AI call\n⚡ Setup takes under an hour — Day 1 live\n\nWant me to roleplay a scenario for your industry?`;
  }

  if (lower.includes('roi') || lower.includes('savings') || lower.includes('save')) {
    return `Let's talk savings!\n\n💰 Starter saves ~$168K/yr vs hiring\n📊 Growth saves ~$216K/yr\n🚀 High saves ~$336K/yr\n📉 That's 85-92% cost reduction from day one\n\nWhat's your current monthly support spend?`;
  }

  // Default
  return `Great question! Let me help you with that.\n\n🎯 PARWA handles 24/7 customer support across all channels\n💡 Plans start at $999/mo with 85%+ savings vs hiring\n🚀 I can demo any scenario you'd like\n\nWhat would you like to explore first?`;
}

// ── Bullet-Point Format Enforcer ────────────────────────────────

function isEmojiChar(ch: string): boolean {
  const code = ch.codePointAt(0) || 0;
  return (
    (code >= 0x1f300 && code <= 0x1faff) ||
    (code >= 0x2600 && code <= 0x27bf) ||
    (code >= 0xfe00 && code <= 0xfe0f)
  );
}

function forceBulletFormat(text: string): string {
  const lines = text.split('\n');
  if (lines.length === 0) return text;

  const nonEmpty = lines.filter((l) => l.trim());
  if (nonEmpty.length === 0) return text;

  const bulletCount = nonEmpty.filter((l) => {
    const t = l.trim();
    return (
      /^[\u2022\-*•]\s/.test(t) ||
      /^[0-9]+[.)]\s/.test(t) ||
      isEmojiChar(t)
    );
  }).length;

  // If 40%+ lines are already bullets, return as-is
  if (nonEmpty.length > 2 && bulletCount / nonEmpty.length >= 0.4) return text;

  if (nonEmpty.length <= 2) {
    const hasLongLine = nonEmpty.some((l) => l.trim().length > 150);
    if (!hasLongLine) return text;
  }

  // Convert paragraphs into bullet-point format
  const result: string[] = [];
  let openerUsed = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      result.push('');
      continue;
    }

    if (
      /^[\u2022\-*•]\s/.test(trimmed) ||
      /^[0-9]+[.)]\s/.test(trimmed)
    ) {
      result.push(trimmed);
      continue;
    }

    if (isEmojiChar(trimmed)) {
      result.push(trimmed);
      continue;
    }

    if (trimmed.length < 50) {
      if (!openerUsed) {
        result.push(trimmed);
        openerUsed = true;
      } else {
        const emoji = pickEmoji(trimmed);
        result.push(
          `${emoji} ${trimmed.charAt(0).toUpperCase() + trimmed.slice(1)}`,
        );
      }
      continue;
    }

    const sentences = trimmed.match(/[^.!?]*[.!?]+/g) || [trimmed];
    if (sentences.length === 1 && trimmed.length < 80) {
      result.push(trimmed);
      continue;
    }

    if (sentences.length === 1) {
      const parts = trimmed
        .split(/,/g)
        .map((s) => s.trim())
        .filter(Boolean);
      if (parts.length >= 2) {
        result.push(parts[0]);
        result.push('');
        for (let i = 1; i < parts.length; i++) {
          const p = parts[i].trim();
          if (!p) continue;
          const emoji = pickEmoji(p);
          result.push(
            `${emoji} ${p.charAt(0).toUpperCase() + p.slice(1)}`,
          );
        }
      } else {
        const emoji = pickEmoji(trimmed);
        result.push(
          `${emoji} ${trimmed.charAt(0).toUpperCase() + trimmed.slice(1)}`,
        );
      }
      continue;
    }

    if (!openerUsed) {
      result.push(sentences[0].trim());
      result.push('');
      openerUsed = true;
    }

    for (let i = 1; i < sentences.length; i++) {
      const s = sentences[i].trim();
      if (!s) continue;
      const emoji = pickEmoji(s);
      result.push(`${emoji} ${s.charAt(0).toUpperCase() + s.slice(1)}`);
    }
  }

  return result.join('\n');
}

function pickEmoji(text: string): string {
  const lower = text.toLowerCase();
  if (
    lower.includes('save') ||
    lower.includes('cost') ||
    lower.includes('price') ||
    lower.includes('$')
  )
    return '💰';
  if (
    lower.includes('automat') ||
    lower.includes('ai') ||
    lower.includes('robot') ||
    lower.includes('resolv')
  )
    return '🤖';
  if (
    lower.includes('channel') ||
    lower.includes('email') ||
    lower.includes('chat') ||
    lower.includes('phone')
  )
    return '📡';
  if (
    lower.includes('integrat') ||
    lower.includes('connect') ||
    lower.includes('shopify')
  )
    return '🔗';
  if (lower.includes('secur') || lower.includes('encrypt') || lower.includes('gdpr'))
    return '🔒';
  if (lower.includes('speed') || lower.includes('fast') || lower.includes('quick'))
    return '⚡';
  if (lower.includes('analyt') || lower.includes('data') || lower.includes('roi'))
    return '📊';
  if (lower.includes('feature') || lower.includes('capab') || lower.includes('support'))
    return '🎯';
  if (lower.includes('start') || lower.includes('begin') || lower.includes('get'))
    return '🚀';
  if (lower.includes('check') || lower.includes('yes') || lower.includes('sure'))
    return '✅';
  if (lower.includes('think') || lower.includes('smart') || lower.includes('predict'))
    return '🧠';
  return '💡';
}

// ── In-Memory Session Store (Local Fallback) ────────────────────

const sessions = new Map();

function generateId(): string {
  return `onb_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function createDefaultSession(
  entrySource?: string,
  entryParams?: Record<string, unknown>,
) {
  const params = entryParams || {};
  const industry = params.industry ? String(params.industry) : null;
  const referralSource = params.utm_source ? String(params.utm_source) : '';
  const preselectedVariant = params.variant ? String(params.variant) : null;
  const preselectedPlan = params.plan ? String(params.plan) : null;

  let effectiveSource = entrySource || 'direct';
  if (params.entry_source) effectiveSource = String(params.entry_source);
  if (industry) effectiveSource = `industry_${industry}`;

  const selectedVariants: string[] = [];
  if (preselectedVariant) selectedVariants.push(preselectedVariant);

  return {
    id: generateId(),
    session_id: generateId(),
    session_type: 'onboarding',
    context: {
      pages_visited: [],
      industry,
      selected_variants: selectedVariants,
      selected_plan: preselectedPlan,
      roi_result: null,
      demo_topics: [],
      concerns_raised: [],
      business_email: null,
      email_verified: false,
      referral_source: referralSource,
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
    pack_expiry: null,
    demo_call_used: false,
    is_active: true,
    payment_status: 'none',
    handoff_completed: false,
    detected_stage: 'welcome',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

// ── Context-Aware Welcome Messages ──────────────────────────────

function getContextAwareWelcome(entrySource: string, ctx: any): string {
  const source = entrySource || 'direct';
  const ep = ctx.entry_params || {};
  const variant = ep.variant || ctx.variant || null;
  const industry = ep.industry || ctx.industry || 'your enterprise';

  const roi = ctx.roi_result || ep.roi_result;
  let savingsStr = '';
  if (roi) {
    const savings = roi.savings_annual || roi.annual_savings || 0;
    if (savings) {
      try {
        const num = Number(savings);
        savingsStr = num > 0 ? `$${num.toLocaleString()}` : '';
      } catch {
        savingsStr = '';
      }
    }
  }

  const welcomes: Record<string, string> = {
    direct:
      "Control Center active. I am Jarvis, your onboarding partner for PARWA. " +
      "I have established a secure link to your support ecosystem. " +
      "How shall we begin your transformation today?",
    pricing: `Strategizing for ${industry}. I see you've been reviewing our premium architecture. I can help you optimize your deployment to maximize every dollar of ROI. Shall we dive into the specific capabilities of our agents?`,
    roi: roi
      ? `Mission Objective: Efficiency. I've finished auditing your calculations for ${industry}. With an estimate of ${savingsStr || 'staggering'} in annual recaptured revenue, your operation is poised for a significant upgrade. Ready to see the blueprint?`
      : "Welcome. I've been auditing your ROI calculations. The numbers suggest massive untapped potential in your current workflow. Shall I demonstrate how we convert those savings into operational reality?",
    demo:
      "System check complete. Ready for high-fidelity simulation. " +
      "For just $1, I can open 500 tactical channels and a 3-minute professional voice demonstration. " +
      "Shall we initiate?",
    features: `Mapping ${industry} requirements to our 700+ feature landscape. I've identified several high-impact nodes that would solve your current bottlenecks. What is the single most critical operational friction point we should address first?`,
    models_page: `I see you've been analyzing our specialized agents for ${industry}. A precise choice. Those specific architectures are engineered for your vertical's unique logic demands. Shall we run a 3-minute live simulation for $1 so you can witness the performance firsthand?`,
  };

  if (variant && source === 'models_page') {
    return (
      `Greetings. I noticed your interest in the ${variant} agent. ` +
      "It is one of my most sophisticated variants, optimized for high-precision operations. " +
      "As your control center, I can demonstrate its logic right here, " +
      "or we can initiate a voice simulation for $1. What is your command?"
    );
  }

  return welcomes[source] || welcomes.direct;
}

// ── Local AI Response Handler ───────────────────────────────────

async function getLocalAIResponse(
  userMessage: string,
  sessionContext: any,
): Promise<string> {
  const systemPrompt = buildOnboardingSystemPrompt(sessionContext, userMessage);

  // Build conversation from recent messages in context
  const messages: Array<{ role: string; content: string }> = [
    { role: 'system', content: systemPrompt },
  ];

  const recentMessages = (sessionContext.messages || []).slice(-10);
  for (const msg of recentMessages) {
    const role = msg.role === 'jarvis' ? 'assistant' : String(msg.role);
    messages.push({ role, content: String(msg.content) });
  }
  messages.push({ role: 'user', content: userMessage });

  // Try z-ai-web-dev-sdk
  try {
    const result = await callZAISDK(messages);
    if (result) {
      return forceBulletFormat(result);
    }
  } catch (error) {
    console.warn(
      '[OnboardingJarvis] Local AI error:',
      (error instanceof Error ? error.message : String(error))?.slice(0, 100),
    );
  }

  // Keyword fallback
  return forceBulletFormat(
    getKeywordFallback(userMessage, sessionContext),
  );
}

// ══════════════════════════════════════════════════════════════════
// HTTP METHOD HANDLERS
// ══════════════════════════════════════════════════════════════════

// ── POST Handler ────────────────────────────────────────────────

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const endpoint = path.join('/');

  try {
    // ── Try backend proxy first for ALL endpoints ──
    const proxyResult = await proxyToBackend(request, path);
    console.log(
      `[OnboardingJarvis] POST /${endpoint} — Backend proxy ${proxyResult ? 'succeeded' : 'failed, using local fallback'}`,
    );
    if (proxyResult) return proxyResult;

    // ── Local fallback when backend is unavailable ──

    // POST /session — Create Session
    if (endpoint === 'session') {
      const body = await request.json();
      const session = createDefaultSession(
        body.entry_source,
        body.entry_params,
      );
      const welcomeContent = getContextAwareWelcome(
        session.context.entry_source,
        session.context,
      );
      (session.messages as any[]).push({
        id: `onb_welcome_${Date.now()}`,
        session_id: session.id,
        role: 'jarvis',
        content: welcomeContent,
        message_type: 'text',
        metadata: { entry_source: session.context.entry_source },
        timestamp: new Date().toISOString(),
      });
      sessions.set(session.id, session);
      return NextResponse.json({
        session_id: session.id,
        session_type: session.session_type,
        context: session.context,
        message_count_today: session.message_count_today,
        total_message_count: session.total_message_count,
        remaining_today: session.remaining_today,
        pack_type: session.pack_type,
        pack_expiry: session.pack_expiry,
        demo_call_used: session.demo_call_used,
        is_active: session.is_active,
        payment_status: session.payment_status,
        handoff_completed: session.handoff_completed,
        detected_stage: session.detected_stage,
      });
    }

    // POST /message — Send Message & Get AI Reply
    if (endpoint === 'message') {
      const body = await request.json();
      const { message, session_id, channel } = body;

      let session = session_id ? sessions.get(session_id) : undefined;
      if (!session) {
        session = createDefaultSession('direct');
        sessions.set(session.id, session);
      }

      // Merge incoming context from frontend
      if (body.context && typeof body.context === 'object') {
        for (const [key, value] of Object.entries(body.context)) {
          if (value !== null && value !== undefined) {
            session.context[key] = value;
          }
        }
        session.updated_at = new Date().toISOString();
        sessions.set(session.id, session);
      }

      if (!message || typeof message !== 'string') {
        return NextResponse.json(
          {
            error: {
              code: 'bad_request',
              message: 'Message content is required',
              details: null,
            },
          },
          { status: 400 },
        );
      }

      // Auto-extract demo_topics and concerns from message
      const lower = message.toLowerCase();
      const topicKeywords: Record<string, string[]> = {
        pricing: ['price', 'pricing', 'plan', 'cost', 'how much'],
        features: ['feature', 'capability', 'what can'],
        demo: ['demo', 'try', 'show me', 'test'],
        roi: ['roi', 'savings', 'save', 'return'],
        integrations: [
          'integration',
          'connect',
          'shopify',
          'slack',
        ],
      };
      for (const [topic, keywords] of Object.entries(topicKeywords)) {
        if (
          keywords.some((kw) => lower.includes(kw)) &&
          !(session.context.demo_topics || []).includes(topic)
        ) {
          if (!session.context.demo_topics) session.context.demo_topics = [];
          session.context.demo_topics.push(topic);
        }
      }
      const concernKeywords: Record<string, string[]> = {
        expensive: ['expensive', 'too much', 'costly', 'overpriced'],
        quality: ['wrong answer', 'dumb', 'mistake', 'inaccurate'],
        security: ['data breach', 'hack', 'privacy', 'unsafe'],
        setup: ['how long', 'setup time', 'complicated'],
      };
      for (const [concern, keywords] of Object.entries(concernKeywords)) {
        if (
          keywords.some((kw) => lower.includes(kw)) &&
          !(session.context.concerns_raised || []).includes(concern)
        ) {
          if (!session.context.concerns_raised)
            session.context.concerns_raised = [];
          session.context.concerns_raised.push(concern);
        }
      }

      // Save user message
      (session.messages as any[]).push({
        id: `user_${Date.now()}`,
        session_id: session.id,
        role: 'user',
        content: message.trim(),
        message_type: 'text',
        metadata: {},
        timestamp: new Date().toISOString(),
      });

      session.message_count_today++;
      session.total_message_count++;
      session.remaining_today = Math.max(
        0,
        (session.pack_type === 'demo' ? 500 : 20) -
          session.message_count_today,
      );

      const newStage = detectStage(message, session.context);
      session.detected_stage = newStage;
      session.context.detected_stage = newStage;

      // Get AI response using local fallback
      const aiContent = await getLocalAIResponse(message, session.context);

      const aiMsg = {
        id: `onb_jarvis_${Date.now()}`,
        session_id: session.id,
        role: 'jarvis',
        content: aiContent,
        message_type: 'text',
        metadata: {},
        timestamp: new Date().toISOString(),
      };
      (session.messages as any[]).push(aiMsg);
      session.updated_at = new Date().toISOString();
      sessions.set(session.id, session);

      return NextResponse.json({
        session_id: session.id,
        content: aiContent,
        message_type: 'text',
        function_called: null,
        function_result: null,
        card_type: 'none',
        card_data: {},
        stage: session.detected_stage,
        remaining_today: session.remaining_today,
        metadata: {},
      });
    }

    // POST /entry — Set Entry Context
    if (endpoint === 'entry') {
      const body = await request.json();
      const { session_id, entry_source, entry_params } = body;

      if (!session_id || !sessions.has(session_id)) {
        // Create new session with entry context
        const session = createDefaultSession(entry_source, entry_params);
        const welcomeContent = getContextAwareWelcome(
          session.context.entry_source,
          session.context,
        );
        (session.messages as any[]).push({
          id: `onb_entry_${Date.now()}`,
          session_id: session.id,
          role: 'jarvis',
          content: welcomeContent,
          message_type: 'text',
          metadata: { entry_source: session.context.entry_source, is_reentry: true },
          timestamp: new Date().toISOString(),
        });
        sessions.set(session.id, session);
        return NextResponse.json({
          session_id: session.id,
          session_type: session.session_type,
          context: session.context,
          message_count_today: session.message_count_today,
          total_message_count: session.total_message_count,
          remaining_today: session.remaining_today,
          pack_type: session.pack_type,
          is_active: session.is_active,
          payment_status: session.payment_status,
          handoff_completed: session.handoff_completed,
          detected_stage: session.detected_stage,
        });
      }

      const session = sessions.get(session_id);
      const params2 = entry_params || {};
      if (params2.industry) session.context.industry = String(params2.industry);
      if (params2.utm_source) session.context.referral_source = String(params2.utm_source);
      if (params2.variant) {
        const variants = session.context.selected_variants || [];
        if (!variants.includes(String(params2.variant))) variants.push(String(params2.variant));
        session.context.selected_variants = variants;
      }
      if (params2.plan) session.context.selected_plan = String(params2.plan);
      if (entry_source) session.context.entry_source = entry_source;
      if (entry_params) session.context.entry_params = { ...session.context.entry_params, ...params2 };

      const welcomeContent = getContextAwareWelcome(session.context.entry_source, session.context);
      (session.messages as any[]).push({
        id: `onb_entry_${Date.now()}`,
        session_id: session.id,
        role: 'jarvis',
        content: welcomeContent,
        message_type: 'text',
        metadata: { entry_source: session.context.entry_source, is_reentry: true },
        timestamp: new Date().toISOString(),
      });

      session.updated_at = new Date().toISOString();
      sessions.set(session_id, session);
      return NextResponse.json({
        session_id: session.id,
        session_type: session.session_type,
        context: session.context,
        message_count_today: session.message_count_today,
        total_message_count: session.total_message_count,
        remaining_today: session.remaining_today,
        pack_type: session.pack_type,
        is_active: session.is_active,
        payment_status: session.payment_status,
        handoff_completed: session.handoff_completed,
        detected_stage: session.detected_stage,
      });
    }

    // POST /demo-pack/purchase
    if (endpoint === 'demo-pack/purchase') {
      const url = new URL(request.url);
      const sessionId =
        url.searchParams.get('session_id') ||
        (await request.json().catch(() => ({}))).session_id;

      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json(
          {
            error: {
              code: 'not_found',
              message: 'Session not found',
              details: null,
            },
          },
          { status: 404 },
        );
      }

      const session = sessions.get(sessionId);
      session.pack_type = 'demo';
      session.remaining_today = 500;
      session.pack_expiry = new Date(
        Date.now() + 7 * 24 * 60 * 60 * 1000,
      ).toISOString();

      (session.messages as any[]).push({
        id: `onb_demo_pack_${Date.now()}`,
        session_id: sessionId,
        role: 'jarvis',
        content: 'Demo pack activated! You now have 500 messages + a 3-minute AI voice call.',
        message_type: 'payment_confirmation',
        metadata: { pack_type: 'demo', amount: 1.08, currency: 'USD' },
        timestamp: new Date().toISOString(),
      });

      session.updated_at = new Date().toISOString();
      sessions.set(sessionId, session);
      return NextResponse.json({
        message: 'Demo pack activated!',
        pack_type: 'demo',
        pack_expiry: session.pack_expiry,
        remaining_today: 500,
        demo_call_remaining: true,
      });
    }

    // POST /verify/send-otp
    if (endpoint === 'verify/send-otp') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      const body = await request.json();

      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json(
          {
            error: {
              code: 'not_found',
              message: 'Session not found',
              details: null,
            },
          },
          { status: 404 },
        );
      }

      const session = sessions.get(sessionId);
      const otp = Math.floor(100000 + Math.random() * 900000).toString();
      session.context.otp = {
        code: otp,
        email: body.email,
        attempts: 0,
        attempts_remaining: 3,
        expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
        status: 'sent',
      };
      sessions.set(sessionId, session);

      return NextResponse.json({
        message: `OTP sent to ${body.email} (demo: ${otp})`,
        status: 'sent',
        attempts_remaining: 3,
        expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
      });
    }

    // POST /verify/verify-otp
    if (endpoint === 'verify/verify-otp') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      const body = await request.json();

      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json(
          {
            error: {
              code: 'not_found',
              message: 'Session not found',
              details: null,
            },
          },
          { status: 404 },
        );
      }

      const session = sessions.get(sessionId);
      const otpData = session.context.otp;

      if (!otpData || otpData.code !== body.code) {
        return NextResponse.json({
          message: 'Invalid OTP code. Please try again.',
          status: 'failed',
          attempts_remaining: Math.max(
            0,
            (Number(otpData?.attempts_remaining || 3)) - 1,
          ),
        });
      }

      session.context.email_verified = true;
      session.context.business_email = body.email || otpData.email;
      session.context.otp = { ...otpData, status: 'verified', verified_at: new Date().toISOString() };
      session.updated_at = new Date().toISOString();
      sessions.set(sessionId, session);

      return NextResponse.json({
        message: 'Email verified successfully!',
        status: 'verified',
        attempts_remaining: Number(otpData?.attempts_remaining),
      });
    }

    // POST /payment/create
    if (endpoint === 'payment/create') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');

      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json(
          {
            error: {
              code: 'not_found',
              message: 'Session not found',
              details: null,
            },
          },
          { status: 404 },
        );
      }

      const session = sessions.get(sessionId);
      const body = await request.json();

      const items: Array<{ name: string; quantity: number; unit_price: number; total: number }> = [];
      const variants = body.variant_ids || [];
      for (const vId of variants) {
        items.push({ name: `PARWA Variant: ${vId}`, quantity: 1, unit_price: 999, total: 999 });
      }
      const subtotal = items.reduce((sum, i) => sum + i.total, 0);
      const tax = Math.round(subtotal * 0.08 * 100) / 100;
      const total = subtotal + tax;

      const transactionId = `txn_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      const checkoutUrl = `https://pay.paddle.com/checkout/${transactionId}?currency=USD`;

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
      session.updated_at = new Date().toISOString();
      sessions.set(sessionId, session);

      return NextResponse.json({
        checkout_url: checkoutUrl,
        transaction_id: transactionId,
        status: 'pending',
        amount: `$${total.toFixed(2)}/mo`,
        currency: 'USD',
        items,
        subtotal,
        tax,
        total,
      });
    }

    // POST /handoff
    if (endpoint === 'handoff') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');

      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json(
          {
            error: {
              code: 'not_found',
              message: 'Session not found',
              details: null,
            },
          },
          { status: 404 },
        );
      }

      const session = sessions.get(sessionId);
      session.handoff_completed = true;
      session.detected_stage = 'handoff';
      session.context.detected_stage = 'handoff';
      session.updated_at = new Date().toISOString();
      sessions.set(sessionId, session);

      return NextResponse.json({
        handoff_completed: true,
        new_session_id: null,
        handoff_at: new Date().toISOString(),
      });
    }

    // Unknown POST endpoint
    return NextResponse.json(
      {
        error: {
          code: 'not_found',
          message: `Unknown endpoint: POST /api/onboarding-jarvis/${endpoint}`,
          details: null,
        },
      },
      { status: 404 },
    );
  } catch (err) {
    console.error(
      '[OnboardingJarvis] POST error:',
      err instanceof Error ? err.message : String(err),
    );
    return NextResponse.json(
      {
        error: {
          code: 'internal_error',
          message: 'Failed to process request',
          details: err instanceof Error ? err.message : String(err),
        },
      },
      { status: 500 },
    );
  }
}

// ── GET Handler ─────────────────────────────────────────────────

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const endpoint = path.join('/');

  try {
    // Try backend proxy first
    const proxyResult = await proxyToBackend(request, path);
    console.log(
      `[OnboardingJarvis] GET /${endpoint} — Backend proxy ${proxyResult ? 'succeeded' : 'failed, using local fallback'}`,
    );
    if (proxyResult) return proxyResult;

    // ── Local fallback ──

    // GET /session
    if (endpoint === 'session') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');

      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json(
          {
            error: {
              code: 'not_found',
              message: 'Session not found',
              details: null,
            },
          },
          { status: 404 },
        );
      }

      const session = sessions.get(sessionId);
      return NextResponse.json({
        session_id: session.id,
        session_type: session.session_type,
        context: session.context,
        message_count_today: session.message_count_today,
        total_message_count: session.total_message_count,
        remaining_today: session.remaining_today,
        pack_type: session.pack_type,
        pack_expiry: session.pack_expiry,
        demo_call_used: session.demo_call_used,
        is_active: session.is_active,
        payment_status: session.payment_status,
        handoff_completed: session.handoff_completed,
        detected_stage: session.detected_stage,
      });
    }

    // GET /history
    if (endpoint === 'history') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      const limit = parseInt(url.searchParams.get('limit') || '50', 10);
      const offset = parseInt(url.searchParams.get('offset') || '0', 10);

      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json({
          messages: [],
          total: 0,
          limit,
          offset,
          has_more: false,
        });
      }

      const session = sessions.get(sessionId);
      const allMessages = session.messages || [];
      const paginatedMessages = allMessages.slice(offset, offset + limit);

      return NextResponse.json({
        messages: paginatedMessages.map((m: any) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          message_type: m.message_type || 'text',
          metadata: m.metadata || {},
          timestamp: m.timestamp,
        })),
        total: allMessages.length,
        limit,
        offset,
        has_more: offset + limit < allMessages.length,
      });
    }

    // GET /demo-pack/status
    if (endpoint === 'demo-pack/status') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');

      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json(
          {
            error: {
              code: 'not_found',
              message: 'Session not found',
              details: null,
            },
          },
          { status: 404 },
        );
      }

      const session = sessions.get(sessionId);
      const limit = session.pack_type === 'demo' ? 500 : 20;
      return NextResponse.json({
        pack_type: session.pack_type,
        remaining_today: session.remaining_today,
        total_allowed: limit,
        pack_expiry: session.pack_expiry,
        demo_call_remaining: !session.demo_call_used,
      });
    }

    // Unknown GET endpoint
    return NextResponse.json(
      {
        error: {
          code: 'not_found',
          message: `Unknown endpoint: GET /api/onboarding-jarvis/${endpoint}`,
          details: null,
        },
      },
      { status: 404 },
    );
  } catch (err) {
    console.error(
      '[OnboardingJarvis] GET error:',
      err instanceof Error ? err.message : String(err),
    );
    return NextResponse.json(
      {
        error: {
          code: 'internal_error',
          message: 'Failed to process request',
          details: err instanceof Error ? err.message : String(err),
        },
      },
      { status: 500 },
    );
  }
}

// ── PATCH Handler ───────────────────────────────────────────────

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const endpoint = path.join('/');

  try {
    // Try backend proxy first
    const proxyResult = await proxyToBackend(request, path);
    console.log(
      `[OnboardingJarvis] PATCH /${endpoint} — Backend proxy ${proxyResult ? 'succeeded' : 'failed, using local fallback'}`,
    );
    if (proxyResult) return proxyResult;

    // ── Local fallback ──

    // PATCH /context
    if (endpoint === 'context') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');

      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json(
          {
            error: {
              code: 'not_found',
              message: 'Session not found',
              details: null,
            },
          },
          { status: 404 },
        );
      }

      const body = await request.json();
      const session = sessions.get(sessionId);

      // Partial merge of context
      for (const [key, value] of Object.entries(body)) {
        if (value !== null && value !== undefined) {
          session.context[key] = value;
        }
      }
      session.updated_at = new Date().toISOString();
      sessions.set(sessionId, session);

      return NextResponse.json({
        session_id: session.id,
        session_type: session.session_type,
        context: session.context,
        message_count_today: session.message_count_today,
        total_message_count: session.total_message_count,
        remaining_today: session.remaining_today,
        pack_type: session.pack_type,
        is_active: session.is_active,
        payment_status: session.payment_status,
        handoff_completed: session.handoff_completed,
        detected_stage: session.detected_stage,
      });
    }

    // Unknown PATCH endpoint
    return NextResponse.json(
      {
        error: {
          code: 'not_found',
          message: `Unknown endpoint: PATCH /api/onboarding-jarvis/${endpoint}`,
          details: null,
        },
      },
      { status: 404 },
    );
  } catch (err) {
    console.error(
      '[OnboardingJarvis] PATCH error:',
      err instanceof Error ? err.message : String(err),
    );
    return NextResponse.json(
      {
        error: {
          code: 'internal_error',
          message: 'Failed to process request',
          details: err instanceof Error ? err.message : String(err),
        },
      },
      { status: 500 },
    );
  }
}

// ── DELETE Handler ──────────────────────────────────────────────

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;

  try {
    // Try backend proxy first
    const proxyResult = await proxyToBackend(request, path);
    console.log(
      `[OnboardingJarvis] DELETE — Backend proxy ${proxyResult ? 'succeeded' : 'failed, using local fallback'}`,
    );
    if (proxyResult) return proxyResult;

    // DELETE is not used by onboarding-jarvis locally, but we handle it for completeness
    return NextResponse.json(
      {
        error: {
          code: 'not_found',
          message: 'DELETE is not supported for onboarding-jarvis endpoints',
          details: null,
        },
      },
      { status: 404 },
    );
  } catch (err) {
    console.error(
      '[OnboardingJarvis] DELETE error:',
      err instanceof Error ? err.message : String(err),
    );
    return NextResponse.json(
      {
        error: {
          code: 'internal_error',
          message: 'Failed to process request',
          details: err instanceof Error ? err.message : String(err),
        },
      },
      { status: 500 },
    );
  }
}
