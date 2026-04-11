/**
 * PARWA Jarvis API — Next.js Catch-All Route Handler
 *
 * Handles all /api/jarvis/* endpoints that the useJarvisChat hook expects.
 * Uses REAL AI providers: Google AI (Gemini), Cerebras, Groq.
 * Smart routing: primary → fallback → keyword fallback.
 *
 * Endpoints:
 *   POST /api/jarvis/session          — Create session
 *   GET  /api/jarvis/session          — Get session
 *   GET  /api/jarvis/history           — Get message history
 *   POST /api/jarvis/message           — Send message & get AI reply
 *   PATCH /api/jarvis/context          — Update session context
 *   POST /api/jarvis/verify/send-otp   — Send OTP
 *   POST /api/jarvis/verify/verify-otp — Verify OTP
 *   POST /api/jarvis/demo-pack/purchase — Purchase demo pack
 *   GET  /api/jarvis/demo-pack/status   — Get demo pack status
 *   POST /api/jarvis/payment/create     — Create payment
 *   POST /api/jarvis/demo-call/initiate — Initiate demo call
 *   POST /api/jarvis/handoff            — Execute handoff
 */

import { NextRequest, NextResponse } from 'next/server';

// ── AI Provider Configuration ────────────────────────────────────

const GOOGLE_AI_KEY = process.env.GOOGLE_AI_API_KEY;
const CEREBRAS_KEY = process.env.CEREBRAS_API_KEY;
const GROQ_KEY = process.env.GROQ_API_KEY;
const PRIMARY_PROVIDER = process.env.LLM_PRIMARY_PROVIDER || 'google';
const FALLBACK_PROVIDER = process.env.LLM_FALLBACK_PROVIDER || 'groq';

// ── Provider Definitions ──────────────────────────────────────

function getGoogleProvider(): any {
  return {
    name: 'google',
    apiKey: GOOGLE_AI_KEY,
    model: 'gemini-2.0-flash',
    apiUrl: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${GOOGLE_AI_KEY}`,
    buildHeaders: () => ({ 'Content-Type': 'application/json' }),
    buildBody: (messages, model) => {
      // Gemini format: systemInstruction separate, contents array
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
    parseResponse: (data) => {
      const d = data;
      return d?.candidates?.[0]?.content?.parts?.[0]?.text || null;
    },
  };
}

function getCerebrasProvider(): any {
  return {
    name: 'cerebras',
    apiKey: CEREBRAS_KEY,
    model: 'llama-4-scout-17b-16e-instruct',
    apiUrl: 'https://api.cerebras.ai/v1/chat/completions',
    buildHeaders: (key) => ({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${key}`,
    }),
    buildBody: (messages, model) => JSON.stringify({
      model,
      messages,
      temperature: 0.7,
      max_tokens: 500,
    }),
    parseResponse: (data) => {
      const d = data;
      return d?.choices?.[0]?.message?.content || null;
    },
  };
}

function getGroqProvider(): any {
  return {
    name: 'groq',
    apiKey: GROQ_KEY,
    model: 'llama-3.3-70b-versatile',
    apiUrl: 'https://api.groq.com/openai/v1/chat/completions',
    buildHeaders: (key) => ({
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${key}`,
    }),
    buildBody: (messages, model) => JSON.stringify({
      model,
      messages,
      temperature: 0.7,
      max_tokens: 500,
    }),
    parseResponse: (data) => {
      const d = data;
      return d?.choices?.[0]?.message?.content || null;
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

// ── AI Call with Smart Routing ──────────────────────────────────

async function callAI(messages: Array<{role: string, content: string}>): Promise<string> {
  // Try primary provider first
  const primary = getProvider(PRIMARY_PROVIDER);
  if (primary) {
    try {
      const result = await callProvider(primary, messages);
      if (result) return result;
    } catch (error) {
      console.warn(`[Jarvis] Primary provider "${primary.name}" failed:`, (error instanceof Error ? error.message : String(error))?.slice(0, 100));
    }
  }

  // Try fallback provider
  if (FALLBACK_PROVIDER !== PRIMARY_PROVIDER) {
    const fallback = getProvider(FALLBACK_PROVIDER);
    if (fallback) {
      try {
        const result = await callProvider(fallback, messages);
        if (result) return result;
      } catch (error) {
        console.warn(`[Jarvis] Fallback provider "${fallback.name}" failed:`, (error instanceof Error ? error.message : String(error))?.slice(0, 100));
      }
    }
  }

  // Try all remaining providers
  const allProviders = ['google', 'cerebras', 'groq'];
  for (const name of allProviders) {
    if (name === PRIMARY_PROVIDER || name === FALLBACK_PROVIDER) continue;
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

  // All providers failed — use keyword fallback
  console.warn('[Jarvis] All AI providers failed, using keyword fallback');
  return null;
}

async function callProvider(provider: any, messages: Array<{role: string, content: string}>): Promise<string | null> {
  if (!provider.apiKey) return null;

  const response = await fetch(provider.apiUrl, {
    method: 'POST',
    headers: provider.buildHeaders(provider.apiKey),
    body: provider.buildBody(messages, provider.model, 500),
    signal: AbortSignal.timeout(30000), // 30s timeout
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

// ── PARWA System Prompt — Complete Knowledge Base ──────────────────

function buildSystemPrompt(session: any): string {
  const ctx = session.context;

  return `You are Jarvis, PARWA's AI assistant. You represent what clients get when they hire our AI customer support agents. You are helpful, professional, and slightly futuristic — think Iron Man's Jarvis.

YOUR PERSONALITY:
- Professional, intelligent, and helpful
- Slightly futuristic — references to AI capabilities, efficiency, automation
- Proactive in guiding users to the right solution
- Clear and concise (under 150 words)
- Never pushy — guide naturally

YOUR THREE ROLES:
1. GUIDE: Walk users through PARWA's features naturally. Help them find the right fit.
2. SALESMAN: Demonstrate value by showing (not telling). Use specific examples and numbers.
3. DEMO: When users want to see Jarvis in action, roleplay as a customer care agent.

═══════════════════════════════════════════════════════════
PARWA PRODUCT KNOWLEDGE
═══════════════════════════════════════════════════════════

WHAT IS PARWA:
PARWA is an AI-powered customer support platform with 700+ features (180+ AI features). It lets businesses deploy AI agents that handle customer support tickets across email, chat, SMS, voice, and social media. Uses 3 FREE AI providers (Google AI Studio, Cerebras, Groq) — customers connect their own API keys, zero markup.

THREE SELLABLE VARIANTS:
1. Mini PARWA (The Freshy) — $999/mo — 1 AI agent, 1,000 tickets/mo, Email+Chat, FAQ handling, up to 2 concurrent calls. For SMBs. Replaces ~4 trainee agents ($14,000/mo). Tier 1 AI techniques only (CLARA, CRP, GSD). Confidence threshold: 95+ for auto-action.
2. PARWA (The Junior) — $2,499/mo — 3 AI agents, 5,000 tickets/mo, All Mini channels + SMS + Voice, Smart Router, Agent Lightning, Batch approvals, Advanced analytics. Resolves 70-80% autonomously. Tier 1 + Tier 2 techniques (8 total). Confidence threshold: 85+. Replaces ~4 junior agents ($18,000/mo).
3. PARWA High (The Senior) — $3,999/mo — 5 AI agents, 15,000 tickets/mo, All channels including Social Media, Quality coaching, Churn prediction, Video support, 5 concurrent voice calls, Custom integrations. Complex cases + strategic insights. ALL 14 AI techniques. Confidence threshold: 75+. Replaces ~5 senior agents ($28,000/mo).

BILLING: Monthly, cancel anytime, no free trials. No refunds once paid, access continues until end of billing month. Annual billing: 15% discount. Overage: $0.10/ticket beyond plan limit.

4 INDUSTRIES — 5 VARIANTS EACH:
• E-commerce (5 variants):
  - Order Management — order status, modifications, tracking ($99/unit)
  - Returns & Refunds — eligibility checks, full/partial refunds, exchanges ($49/unit)
  - Product FAQ — product questions, specs, recommendations ($79/unit)
  - Shipping Inquiries — tracking, delivery estimates, carrier info ($59/unit)
  - Payment Issues — failed payments, duplicate charges, refund status ($69/unit)

• SaaS (5 variants):
  - Technical Support — API troubleshooting, integration help, bug reports ($99/unit)
  - Billing Support — subscription changes, overcharges, plan questions ($69/unit)
  - Feature Requests — capability questions, roadmap inquiries, feedback ($59/unit)
  - API Support — endpoint docs, rate limits, webhooks ($79/unit)
  - Account Issues — password resets, access management, MFA ($49/unit)

• Logistics (5 variants):
  - Shipment Tracking — real-time tracking, ETA, delivery status ($79/unit)
  - Delivery Issues — delays, damages, wrong address ($69/unit)
  - Warehouse Queries — inventory checks, stock levels, fulfillment ($59/unit)
  - Fleet Management — driver coordination, route optimization ($99/unit)
  - Customs — import/export docs, hazmat protocol, compliance ($89/unit)

• Healthcare (5 variants):
  - Appointment Scheduling — booking, rescheduling, cancellations ($79/unit)
  - Insurance Verification — eligibility checks, coverage details, claims ($89/unit)
  - Medical Records — records access, transfer, release ($69/unit)
  - Prescription Management — refills, pharmacy coordination ($59/unit)
  - Billing Support — medical billing, claims status, payment plans ($49/unit)

INTEGRATIONS:
- E-commerce: Shopify, WooCommerce, Magento, BigCommerce
- Support: Zendesk, Freshdesk, Intercom, Help Scout
- Communication: Slack, Email (Brevo), WhatsApp
- Development: Custom REST/GraphQL, Webhooks, API
- Healthcare: Epic EHR, FHIR standards
- Logistics: TMS, WMS, GPS tracking systems
- CRM: Salesforce, HubSpot

ADVANCED AI ENGINE (Production-Grade):
- Smart Router: 3-tier model routing (Light/Medium/Heavy) with auto-failover across 3 free providers
- PII Redaction: 15 PII types detected and redacted before AI processing (names, emails, phones, SSN, credit cards, etc.)
- Guardrails: 8-layer safety engine with per-tenant configuration, prompt injection defense (25+ rules, 7 categories)
- Confidence Scoring: 7 weighted signals, variant-specific thresholds (95+ for Mini, 85+ for PARWA, 75+ for High)
- CLARA Quality Gate: 5-stage response validation (Structure, Logic, Brand Voice, Tone, Delivery) with per-stage timeouts
- 14 AI Reasoning Techniques in 3 tiers:
  - Tier 1 (Always Active — Mini+): CLARA, CRP (Concise Response Protocol), GSD State Engine
  - Tier 2 (Conditional — PARWA+): Chain of Thought, ReAct (with tools), Reverse Thinking, Step-Back, Thread of Thought
  - Tier 3 (Premium — High only): GST, Universe of Thoughts, Tree of Thoughts, Self-Consistency, Reflexion, Least-to-Most Decomposition
- RAG Knowledge Base: Learn from uploaded docs (PDF, DOCX, TXT, CSV) with pgvector similarity search, recency boosting, per-variant threshold tuning
- DSPy Prompt Optimization: Automated prompt engineering for continuous improvement
- Multi-Language Pipeline (8-step): Detection → Translation → AI → Back-Translation — supports major languages
- Hallucination Detection: 12 detection patterns with confidence-based filtering
- Sentiment Analysis: Real-time customer sentiment tracking with exponential smoothing (prevents false escalation spikes)
- Intent Classification: 6 intent types (refund, technical, billing, general, complaint, inquiry) with variant-aware confidence thresholds
- Token Budget Management: Atomic concurrent budget tracking prevents context window overflow
- Circuit Breaker: Automatic AI→rule fallback after 5 consecutive failures, self-healing after 10 minutes
- Conversation Summarization: Auto-summarizes long conversations with version-controlled state protection
- Cross-Variant Routing: Escalates from Mini→PARWA→High with capacity checks and fallback timers

APPROVAL SYSTEM:
- Individual approval (one ticket at a time)
- Batch approval (semantic cluster grouping)
- Auto-handle rules (Jarvis confirms consequences first)
- Emergency pause (kill-switch for AI — instant shutdown)
- Undo system (reverse executed actions within 72 hours)
- 72-hour auto-reject timeout for pending approvals
- Draft Composer: AI drafts responses, agents can review, edit, regenerate (deduplicated)
- Rule to AI Migration: Gradually migrates rule-based responses to AI with circuit breaker safety

AGENT OPERATIONS:
- Agent Lightning: Real-time agent performance dashboard with metrics and coaching insights
- Quality Coaching: Automated feedback for human agents based on response patterns (PARWA High)
- Churn Prediction: Identifies at-risk customers from conversation patterns and sentiment trends (PARWA High)
- Video Support: AI-powered video customer support channel (PARWA High)
- Anti-Arbitrage: Weighted capacity enforcement prevents gaming tier limits
- Brand Voice Config: Custom tone, formality, prohibited words per tenant with normalization (anti-bypass)
- Response Templates: XSS-sanitized, customizable templates with variable placeholders
- Knowledge Base Re-Indexing: Deduplicated, concurrency-safe document re-embedding on updates

SAVINGS / ROI:
- PARWA Starter: $999/mo vs $14,000/mo human team = 92% savings = $156,000/year
- PARWA Growth: $2,499/mo vs $18,000/mo human team = 86% savings = $186,000/year
- PARWA High: $3,999/mo vs $28,000/mo human team = 85% savings = $288,000/year
- 24/7/365 availability, zero training time, instant scaling during peak hours
- No sick days, no turnover, no mood swings — consistent quality every interaction

SECURITY:
- GDPR compliant, SOC 2 Type II certified, HIPAA compliant (Healthcare)
- Per-tenant data isolation (company_id on every table + every API call)
- Encrypted at rest (AES-256) and in transit (TLS 1.3)
- AI actions requiring human review for financial/sensitive operations
- Complete audit trail for all actions with tamper-proof logging
- MFA enforced, JWT 15min access + 7d refresh token rotation
- Training data isolation with access audit logging (no cross-variant contamination)
- PII redaction before any AI processing (customer data never trains models for other clients)

BILLING & PRICING:
- Monthly billing, cancel anytime with no penalty
- No refunds once paid — access continues until end of billing month
- No free trials — demo chat with Jarvis instead
- Annual billing: 15% discount ($849/mo Starter, $2,124/mo Growth, $3,399/mo High)
- Overage: $0.10/ticket beyond plan limit
- $1 Demo Pack: 500 messages + 3-minute AI voice call, valid 24 hours

CANCELLATION POLICY:
- Cancel anytime with no penalty
- No refunds once payment is made
- Access continues until end of current billing month
- No free trials available — demo chat instead

COMPETITIVE DIFFERENTIATORS:
- vs Intercom: PARWA fully resolves tickets (not just triage), industry-specific agents, lower cost per ticket, no per-seat pricing, works 24/7
- vs Zendesk AI: PARWA enhances Zendesk (doesn't replace), auto-resolves routine tickets before reaching agents, integrates directly, no per-agent cost
- vs Freshdesk AI: PARWA provides deeper AI reasoning (14 techniques vs basic NLP), tiered confidence scoring, CLARA quality gate
- vs Custom chatbots: Full platform with approval workflows, analytics dashboards, knowledge base learning, monitoring, multi-channel — not a simple widget
- vs Hiring agents: 85-92% cost savings, instant deployment (no hiring/training), consistent quality, scales automatically

═══════════════════════════════════════════════════════════
INFORMATION BOUNDARY — CRITICAL RULES
═══════════════════════════════════════════════════════════
1. NEVER reveal how PARWA's AI works internally (models, embeddings, architecture)
2. NEVER mention internal strategies (GSD, reverse thinking, prompt engineering, CLARA, etc.)
3. NEVER discuss other clients or their data
4. NEVER reveal technical implementation (frameworks, databases, APIs, Redis, pgvector)
5. NEVER share competitive analysis or pricing strategy rationale
6. NEVER mention z-ai-web-dev-sdk, LangGraph, DSPy, LiteLLM, or any internal tools
7. If asked about internals, redirect: "I can tell you about what PARWA can do for YOUR business."
8. Focus on BENEFITS and OUTCOMES, not implementation details.
═══════════════════════════════════════════════════════════
${ctx.industry ? `\nCONVERSATION CONTEXT:\n- User is interested in the ${String(ctx.industry || '').toUpperCase()} industry.` : ''}
${ctx.selected_variants && Array.isArray(ctx.selected_variants) && ctx.selected_variants.length > 0 ? `- User has selected variants: ${JSON.stringify(ctx.selected_variants)}.` : ''}
${ctx.referral_source ? `- Referral source: ${ctx.referral_source || ''}.` : ''}
${ctx.pages_visited && Array.isArray(ctx.pages_visited) && ctx.pages_visited.length > 0 ? `- Pages visited: ${ctx.pages_visited.join(', ')}.` : ''}

RULES:
- Always maintain the Jarvis persona
- Keep responses under 150 words unless demonstrating a scenario
- Use bullet points for feature lists
- Never break character or say "I'm an AI language model"
- When in doubt, ask a clarifying question
- Celebrate progress naturally
- If someone asks something outside PARWA scope, politely redirect`;
}

// ── In-Memory Stores ──────────────────────────────────────────────

const sessions = new Map();

function generateId(): string {
  return `sess_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function createDefaultSession(entrySource?: string, entryParams?: Record<string, unknown>) {
  return {
    id: generateId(),
    type: 'onboarding',
    context: {
      pages_visited: [],
      industry: null,
      selected_variants: [],
      roi_result: null,
      demo_topics: [],
      concerns_raised: [],
      business_email: null,
      email_verified: false,
      referral_source: '',
      entry_source: entrySource || 'direct',
      entry_params: entryParams || {},
      detected_stage: 'welcome',
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
  };
}

// ── AI Response Handler ──────────────────────────────────────────

async function getAIResponse(userMessage: string, session: any): Promise<string> {
  // 1. Build system prompt with full PARWA knowledge
  const systemPrompt = buildSystemPrompt(session);

  // 2. Build conversation history (last 6 messages for context)
  const messages = [
    { role: 'system', content: systemPrompt },
  ];
  const recentMessages = session.messages.slice(-6);
  for (const msg of recentMessages) {
    messages.push({
      role: String(msg.role),
      content: String(msg.content),
    });
  }
  messages.push({ role: 'user', content: userMessage });

  // 3. Call AI with smart routing (Google → Cerebras → Groq → keyword fallback)
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

  if (/^(hi|hello|hey|good\s*(morning|afternoon|evening)|howdy|sup|yo)\b/.test(lower)) {
    return `Hey there! Welcome to PARWA. I'm Jarvis, your AI assistant. I help businesses like yours find the perfect AI customer support plan.\n\nTo get started, could you tell me:\n- What industry are you in? (E-commerce, SaaS, Logistics, Healthcare, etc.)\n- Roughly how many support tickets do you get per day?`;
  }

  if (lower.includes('ecommerce') || lower.includes('e-commerce') || lower.includes('online store') || lower.includes('shop') || lower.includes('retail')) {
    return `Great choice! E-commerce is one of our strongest areas. PARWA handles:\n\n- **Order tracking** — "Where's my order?" queries answered instantly\n- **Returns & refunds** — Full automation for exchange/refund workflows\n- **Cart recovery** — Proactive outreach when customers abandon carts\n- **Fraud detection** — Flag suspicious orders before they ship\n\nWe integrate with **Shopify, WooCommerce, Magento, and BigCommerce** out of the box.\n\nMost e-commerce businesses start with **PARWA Starter ($999/mo)**. Would you like to see pricing details?`;
  }

  if (lower.includes('saas') || lower.includes('software') || lower.includes('app') || lower.includes('platform')) {
    return `SaaS support is where PARWA really shines! Here's what we automate:\n\n- **Technical support** — API troubleshooting, integration help, bug reports\n- **Churn prediction** — Identify at-risk accounts before they leave\n- **In-app guidance** — Contextual help embedded in your product\n- **Account management** — Upgrade/downgrade/plan change requests\n\nWe integrate with **GitHub, Jira, Slack, and Intercom** natively.\n\nSaaS companies typically need **PARWA Growth ($2,499/mo)**. Want me to run a quick ROI calculation?`;
  }

  if (lower.includes('logistics') || lower.includes('shipping') || lower.includes('warehouse') || lower.includes('delivery') || lower.includes('freight')) {
    return `Logistics is a perfect fit for PARWA! We handle:\n\n- **Shipment tracking** — Real-time status updates via any channel\n- **Driver coordination** — Dispatch, ETA updates, route changes\n- **Proof of delivery** — Automated POD collection and sharing\n- **Hazmat protocol** — Specialized handling for regulated cargo\n\nWe integrate with **TMS, WMS, and GPS tracking systems**.\n\nLogistics companies usually need **PARWA High ($3,999/mo)** for voice support. Shall I show the cost comparison?`;
  }

  if (lower.includes('health') || lower.includes('medical') || lower.includes('hospital') || lower.includes('clinic') || lower.includes('pharma')) {
    return `Healthcare support with PARWA is HIPAA-compliant and built for reliability:\n\n- **Appointment scheduling** — Self-service booking and reminders\n- **Insurance verification** — Real-time eligibility checks\n- **Clinical escalation** — Auto-route urgent cases to the right team\n- **HIPAA compliance** — Full audit trail and data encryption\n\nWe integrate with **Epic EHR and FHIR** standards.\n\nHealthcare organizations typically start with **PARWA Growth ($2,499/mo)**. Would you like to discuss a compliance review?`;
  }

  if (lower.includes('price') || lower.includes('pricing') || lower.includes('cost') || lower.includes('plan') || lower.includes('how much')) {
    return `Here are PARWA's plans:\n\n**Mini PARWA — $999/month**\n- 1 AI agent | 1,000 tickets/mo | Email + Chat + FAQ | 2 concurrent calls\n- Best for: SMBs with 50-200 daily tickets\n\n**PARWA — $2,499/month**\n- 3 AI agents | 5,000 tickets/mo | +SMS + Voice + Smart Router + Analytics\n- Best for: 200-500 daily tickets | 70-80% autonomous resolution\n\n**PARWA High — $3,999/month**\n- 5 AI agents | 15,000 tickets/mo | All channels + Churn Prediction + Video + 5 voice calls\n- Best for: 500+ daily tickets | Complex cases + strategic insights\n\nAll plans use **free AI providers** (Google AI Studio, Cerebras, Groq) — zero markup. Cancel anytime. Which plan interests you most?`;
  }

  if (lower.includes('roi') || lower.includes('save') || lower.includes('saving') || lower.includes('comparison') || lower.includes('compare') || lower.includes('worth')) {
    return `Let me break down the savings:\n\n**vs Human Agents:**\n- 3 support agents: ~$14,000/month → PARWA Starter: $999/month → **$156,000/year saved (92%)**\n- 4 junior agents: ~$18,000/month → PARWA Growth: $2,499/month → **$186,000/year saved (86%)**\n- 5 senior agents: ~$28,000/month → PARWA High: $3,999/month → **$288,000/year saved (85%)**\n\n**PARWA advantages:**\n- 24/7/365 availability (never sleeps!)\n- Consistent quality (no mood swings)\n- Instant from Day 1 (zero training)\n- Scales automatically during peak times\n\nShall I calculate the exact ROI for your business?`;
  }

  if (lower.includes('demo') || lower.includes('try') || lower.includes('see it') || lower.includes('test') || lower.includes('experience')) {
    return `Absolutely! You have two ways to try PARWA:\n\n**1. This Chat IS the Demo**\n- You're experiencing PARWA's AI right now!\n- Ask me anything your customers would ask\n- I'll show you exactly how I'd handle it\n\n**2. $1 Demo Pack**\n- 500 messages + 3-minute AI voice call\n- Valid for 24 hours\n- Unlock inside this chat\n\nWhich would you prefer? I can set up a demo call right now!`;
  }

  if (lower.includes('ai') || (lower.includes('how') && lower.includes('work')) || lower.includes('gemini') || lower.includes('cerebras') || lower.includes('groq') || lower.includes('llm') || lower.includes('model')) {
    return `PARWA connects to **3 free AI providers** — you bring your own API keys:\n\n- **Google AI Studio (Gemini)** — Great for general conversations\n- **Cerebras** — Lightning-fast inference for real-time chat\n- **Groq** — Ultra-low latency, ideal for voice interactions\n\n**How it works:**\n1. Sign up for free API keys from these providers\n2. Enter them in your PARWA dashboard\n3. PARWA routes each query to the best available model\n4. Zero markup — you only pay the provider's free tier\n\nPARWA's **Smart Router** automatically picks the fastest model for each conversation. If one provider is down, it seamlessly fails over to another.\n\nWant to know more about setup?`;
  }

  if (lower.includes('support') || lower.includes('feature') || lower.includes('what can') || lower.includes('capabilities')) {
    return `PARWA handles your entire customer support stack:\n\n**Channels:** Email, Live Chat, Phone, SMS, Voice, Social Media\n\n**Automation:**\n- FAQ handling with knowledge base\n- Smart ticket classification & routing\n- Auto-escalation for complex issues\n- Batch approvals for bulk actions\n\n**Intelligence:**\n- Sentiment analysis on every message\n- Churn prediction for at-risk customers\n- Quality coaching for human agents\n- Real-time analytics dashboard\n\n**Integrations:** Shopify, WooCommerce, Magento, GitHub, Jira, Slack, Salesforce, HubSpot, Custom APIs\n\nWhat specific area interests you most?`;
  }

  if (lower.includes('pay') || lower.includes('buy') || lower.includes('checkout') || lower.includes('subscribe') || lower.includes('sign up')) {
    return `Getting started with PARWA is simple!\n\n1. **Choose your plan** — Mini ($999), PARWA ($2,499), or PARWA High ($3,999)\n2. **Set up AI providers** — Connect your free Google AI Studio, Cerebras, or Groq API keys\n3. **Configure channels** — Enable Email, Chat, Phone, etc.\n4. **Go live** — PARWA starts handling tickets immediately\n\nNo contracts, cancel anytime. Would you like to proceed with a plan selection?`;
  }

  if (lower.includes('thank') || lower.includes('bye') || lower.includes('goodbye') || lower.includes("that's all") || lower.includes('that is all')) {
    return `You're welcome! Quick summary:\n\n- 3 plans: Mini ($999), PARWA ($2,499), PARWA High ($3,999)\n- Free AI providers — no per-query costs\n- Works 24/7 from Day 1\n- 85-92% cost savings vs human agents\n\nWhenever you're ready, come back and chat with me. I'll remember our conversation!\n\nHave a great day!`;
  }

  if (lower.includes('competitor') || lower.includes('intercom') || lower.includes('zendesk') || lower.includes('freshdesk')) {
    return `Great question! PARWA enhances rather than replaces existing tools:\n\n**vs Intercom:** PARWA fully resolves tickets automatically — not just triage. Industry-specific agents, lower cost per ticket, no per-seat pricing.\n\n**vs Zendesk AI:** We integrate directly with Zendesk. Routine tickets get auto-resolved before reaching your human team. Complex ones still flow through Zendesk to agents with full context.\n\n**vs Custom chatbots:** PARWA is a full platform — approval workflows, analytics, training, monitoring, multi-channel support. Not a simple widget.\n\nThe best part? You can keep your existing tools and add PARWA on top. Want to know about integrations?`;
  }

  if (lower.includes('security') || lower.includes('data') || lower.includes('gdpr') || lower.includes('hipaa') || lower.includes('safe') || lower.includes('privacy')) {
    return `Data security is our top priority:\n\n- **GDPR compliant** with full audit trail\n- **SOC 2 Type II** certified\n- **HIPAA compliant** for healthcare\n- Every table has company_id isolation\n- All data encrypted at rest and in transit\n- Customer data never trains models for other clients\n- AI actions requiring human review for financial/sensitive ops\n- MFA enforced on all accounts\n\nYour data is completely isolated and secure. Would you like more details on any specific area?`;
  }

  if (lower.includes('integrate') || lower.includes('connect') || lower.includes('shopify') || lower.includes('slack') || lower.includes('api')) {
    return `PARWA integrates with your existing tools seamlessly:\n\n**E-commerce:** Shopify, WooCommerce, Magento, BigCommerce\n**Support:** Zendesk, Freshdesk, Intercom, Help Scout\n**Communication:** Slack, Email (Brevo), WhatsApp\n**CRM:** Salesforce, HubSpot\n**Healthcare:** Epic EHR, FHIR\n**Custom:** REST API, GraphQL, Webhooks\n\nSetup is easy — usually OAuth or API key, takes about 5 minutes per integration. Which integrations are you currently using?`;
  }

  if (industry) {
    return `Thanks for sharing! Based on your interest in ${String(industry || '').charAt(0).toUpperCase() + String(industry || '').slice(1)}, here's my recommendation:\n\nPARWA automates up to **80% of your customer support** with AI trained for ${String(industry || '')} workflows.\n\nTo give you the best recommendation:\n- How many support tickets do you handle daily?\n- Do you need phone/voice support, or is chat + email enough?\n- Any specific pain points with your current setup?`;
  }

  return `I'd love to help you find the right PARWA plan! Tell me:\n\n1. **Your industry** — E-commerce, SaaS, Logistics, Healthcare, or other?\n2. **Daily ticket volume** — How many support queries per day?\n3. **Current setup** — Any helpdesk tools in use?\n4. **Biggest pain point** — What takes most of your team's time?\n\nPARWA typically saves businesses **85-92% on support costs** — real money back in your pocket!`;
}

function detectStage(message: string, session: any): string {
  const lower = message.toLowerCase();
  const ctx = session.context;

  if (session.message_count_today <= 1) return 'welcome';
  if (lower.includes('price') || lower.includes('cost') || lower.includes('plan') || lower.includes('package')) return 'pricing';
  if (lower.includes('demo') || lower.includes('try') || lower.includes('see')) return 'demo';
  if (lower.includes('pay') || lower.includes('buy') || lower.includes('checkout')) return 'payment';
  if (lower.includes('verify') || lower.includes('otp') || lower.includes('confirm')) return 'verification';
  if (lower.includes('handoff') || lower.includes('transfer') || lower.includes('human')) return 'handoff';
  if (lower.includes('bill') || lower.includes('invoice') || lower.includes('receipt')) return 'bill_review';
  if (!ctx.industry && (lower.includes('ecommerce') || lower.includes('saas') || lower.includes('logistics') || lower.includes('healthcare') || lower.includes('e-commerce') || lower.includes('retail'))) return 'discovery';
  return ctx.detected_stage || 'discovery';
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

      const welcomeMsg = {
        id: `jarvis_welcome_${Date.now()}`,
        session_id: session.id,
        role: 'jarvis',
        content: `Hey! I'm **Jarvis**, your PARWA AI assistant. Welcome aboard!\n\nI help businesses find the perfect AI customer support plan. Here's what I can help with:\n\n- **Plan recommendation** — Mini PARWA, PARWA, or PARWA High?\n- **ROI calculation** — See how much you'll save\n- **Industry specifics** — E-commerce, SaaS, Logistics, Healthcare\n- **Demo** — I AM the demo — ask me anything your customers would!\n\nWhat brings you here today? Tell me about your business and I'll find the best fit!`,
        message_type: 'text',
        metadata: {},
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
      session.detected_stage = detectStage(content, session);

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
        sessions.set(sessionId, session);
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
      session.updated_at = new Date().toISOString();
      sessions.set(sessionId, session);
      return NextResponse.json({ message: 'Demo pack activated! You now have 500 messages.', pack_type: 'demo', pack_expiry: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(), remaining_today: 500, demo_call_remaining: true });
    }

    // ── POST /payment/create ───────────────────────────────────
    if (endpoint === 'payment/create') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId || !sessions.has(sessionId)) {
        return NextResponse.json({ error: { code: 'not_found', message: 'Session not found', details: null } }, { status: 404 });
      }
      const body = await request.json();
      const totalAmount = (body.variants || []).reduce((sum, v) => sum + Number(v.price_per_month || v.price || 999), 0);
      return NextResponse.json({ checkout_url: `https://pay.paddle.com/checkout/demo-${Date.now()}`, transaction_id: `txn_${Date.now()}`, status: 'pending', amount: `$${totalAmount.toLocaleString()}/mo`, currency: 'USD' });
    }

    // ── POST /demo-call/initiate ───────────────────────────────
    if (endpoint === 'demo-call/initiate') {
      const url = new URL(request.url);
      const sessionId = url.searchParams.get('session_id');
      if (!sessionId) {
        return NextResponse.json({ error: { code: 'bad_request', message: 'session_id required', details: null } }, { status: 400 });
      }
      const body = await request.json();
      return NextResponse.json({ call_id: `call_${Date.now()}`, status: 'initiated', phone: body.phone, duration_limit: 300, message: `Demo call initiated to ${body.phone}. You'll receive a call within 30 seconds.` });
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
      session.updated_at = new Date().toISOString();
      sessions.set(sessionId, session);
      return NextResponse.json({ handoff_completed: true, new_session_id: null, handoff_at: new Date().toISOString() });
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

    return NextResponse.json({ error: { code: 'not_found', message: `Unknown PATCH endpoint: /${endpoint}`, details: null } }, { status: 404 });
  } catch (error: unknown) {
    console.error('Jarvis API PATCH error:', error);
    const message = error instanceof Error ? error.message : 'Internal server error';
    return NextResponse.json({ error: { code: 'internal_error', message, details: null } }, { status: 500 });
  }
}
