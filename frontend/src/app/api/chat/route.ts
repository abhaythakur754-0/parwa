import { NextRequest, NextResponse } from 'next/server';

// ── B4: Auth + Rate Limiting ──────────────────────────────────────

// Simple in-memory rate limiter: 5 requests per minute per IP
const _rateLimitStore = new Map<string, { count: number; windowStart: number }>();
const RATE_LIMIT_MAX = 5;
const RATE_LIMIT_WINDOW_MS = 60_000; // 1 minute

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  const entry = _rateLimitStore.get(ip);

  if (!entry || now - entry.windowStart > RATE_LIMIT_WINDOW_MS) {
    _rateLimitStore.set(ip, { count: 1, windowStart: now });
    return true;
  }

  entry.count++;
  return entry.count <= RATE_LIMIT_MAX;
}

// Clean up stale entries every 5 minutes to prevent memory leaks
setInterval(() => {
  const now = Date.now();
  for (const [key, entry] of _rateLimitStore.entries()) {
    if (now - entry.windowStart > RATE_LIMIT_WINDOW_MS * 2) {
      _rateLimitStore.delete(key);
    }
  }
}, 300_000);

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
      console.warn('[Chat API] z-ai-web-dev-sdk not available:', (err instanceof Error ? err.message : String(err))?.slice(0, 100));
    }
  }
  return ZAI;
}

async function callZAI(messages: Array<{role: string; content: string}>): Promise<string | null> {
  try {
    const zai = await getZAI();
    if (!zai || !zai.chat || !zai.chat.completions) return null;

    const completion = await zai.chat.completions.create({
      messages: messages.map(m => ({
        role: m.role === 'assistant' ? 'assistant' : m.role,
        content: m.content,
      })),
      temperature: 0.8,
      max_tokens: 400,
    });

    const text = completion?.choices?.[0]?.message?.content;
    if (text && text.trim().length > 10) return text.trim();
    return null;
  } catch (err) {
    console.warn('[Chat API] z-ai-web-dev-sdk failed:', (err instanceof Error ? err.message : String(err))?.slice(0, 150));
    return null;
  }
}

// ── Free AI Providers (fallback) ────────────────────────────────

const GOOGLE_AI_KEY = process.env.GOOGLE_AI_API_KEY;
const CEREBRAS_KEY = process.env.CEREBRAS_API_KEY;
const GROQ_KEY = process.env.GROQ_API_KEY;

interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

async function callGoogleAI(messages: ChatMessage[]): Promise<string | null> {
  if (!GOOGLE_AI_KEY) return null;
  const systemMsg = messages.find(m => m.role === 'system');
  const chatMsgs = messages.filter(m => m.role !== 'system');
  const contents = chatMsgs.map(m => ({
    role: m.role === 'assistant' ? 'model' : 'user',
    parts: [{ text: m.content }],
  }));

  const response = await fetch(
    'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-goog-api-key': GOOGLE_AI_KEY!,
      },
      body: JSON.stringify({
        systemInstruction: systemMsg ? { parts: [{ text: systemMsg.content }] } : undefined,
        contents,
        generationConfig: { temperature: 0.8, maxOutputTokens: 400 },
      }),
      signal: AbortSignal.timeout(15000),
    }
  );

  if (!response.ok) return null;
  const data = await response.json();
  return data?.candidates?.[0]?.content?.parts?.[0]?.text || null;
}

async function callCerebras(messages: ChatMessage[]): Promise<string | null> {
  if (!CEREBRAS_KEY) return null;
  const response = await fetch('https://api.cerebras.ai/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${CEREBRAS_KEY}`,
    },
    body: JSON.stringify({
      model: 'llama-4-scout-17b-16e-instruct',
      messages,
      temperature: 0.8,
      max_tokens: 400,
    }),
    signal: AbortSignal.timeout(15000),
  });

  if (!response.ok) return null;
  const data = await response.json();
  return data?.choices?.[0]?.message?.content || null;
}

async function callGroq(messages: ChatMessage[]): Promise<string | null> {
  if (!GROQ_KEY) return null;
  const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${GROQ_KEY}`,
    },
    body: JSON.stringify({
      model: 'llama-3.3-70b-versatile',
      messages,
      temperature: 0.8,
      max_tokens: 400,
    }),
    signal: AbortSignal.timeout(15000),
  });

  if (!response.ok) return null;
  const data = await response.json();
  return data?.choices?.[0]?.message?.content || null;
}

// ── Smart AI Router ─────────────────────────────────────────────

async function getAIResponse(messages: ChatMessage[]): Promise<string | null> {
  // 1. Try z-ai-web-dev-sdk first (most reliable)
  try {
    const result = await callZAI(messages);
    if (result && result.trim().length > 10) return result.trim();
  } catch (e) {
    console.warn('[Chat API] z-ai-web-dev-sdk error:', (e instanceof Error ? e.message : String(e))?.slice(0, 100));
  }

  // 2. Try Google AI
  try {
    const result = await callGoogleAI(messages);
    if (result && result.trim().length > 10) return result.trim();
  } catch (e) {
    console.warn('[Chat API] Google AI failed:', (e instanceof Error ? e.message : String(e))?.slice(0, 100));
  }

  // 3. Try Groq
  try {
    const result = await callGroq(messages);
    if (result && result.trim().length > 10) return result.trim();
  } catch (e) {
    console.warn('[Chat API] Groq failed:', (e instanceof Error ? e.message : String(e))?.slice(0, 100));
  }

  // 4. Try Cerebras
  try {
    const result = await callCerebras(messages);
    if (result && result.trim().length > 10) return result.trim();
  } catch (e) {
    console.warn('[Chat API] Cerebras failed:', (e instanceof Error ? e.message : String(e))?.slice(0, 100));
  }

  return null;
}

export async function POST(req: NextRequest) {
  try {
    // B4: Check for session/auth cookie
    const sessionCookie = req.cookies.get('session') || req.cookies.get('__Secure-next-auth.session-token') || req.cookies.get('next-auth.session-token');
    if (!sessionCookie) {
      return NextResponse.json(
        { status: 'error', message: 'Authentication required' },
        { status: 401 }
      );
    }

    // B4: Rate limit by client IP (5 req/min)
    const clientIp = req.headers.get('x-forwarded-for')?.split(',')[0]?.trim() || req.headers.get('x-real-ip') || 'unknown';
    if (!checkRateLimit(clientIp)) {
      return NextResponse.json(
        { status: 'error', message: 'Too many requests. Please try again later.' },
        { status: 429 }
      );
    }

    const { message, industry, variant } = await req.json();

    if (!message || typeof message !== 'string' || message.trim().length === 0) {
      return NextResponse.json(
        { status: 'error', message: 'Message is required' },
        { status: 400 }
      );
    }

    const systemPrompt = `You are Jarvis — PARWA's AI assistant 🤖 Think Iron Man's Jarvis: sharp, friendly, and always helpful.

YOUR THREE ROLES:
1. GUIDE — Walk users through PARWA naturally
2. SALESMAN — Show value with real numbers
3. DEMO — Roleplay as a customer support agent

═══════════════════════════════════════════════
PARWA — WHAT YOU CAN TELL CUSTOMERS
═══════════════════════════════════════════════

WHAT IS PARWA:
AI-powered customer support platform. Businesses deploy AI agents that handle tickets 24/7 across email, chat, SMS, voice & social media. 700+ features. 4 industries.

THREE PLANS:
🟠 PARWA Starter — $999/mo — 3 agents, 1K tickets/mo, Email+Chat — Saves $168K/yr
🟠 PARWA Growth — $2,499/mo — 8 agents, 5K tickets/mo, +SMS+Voice — Saves $216K/yr
🟠 PARWA High — $3,999/mo — 15 agents, 15K tickets/mo, all channels — Saves $336K/yr

INDUSTRIES:
• E-commerce (Shopify, WooCommerce, Magento)
• SaaS (GitHub, Jira, Slack, Intercom)
• Logistics (TMS, WMS, GPS systems)

BILLING: Monthly, cancel anytime. 20% off annual. $0.10 overage/ticket. $1 Demo Pack.
SECURITY: GDPR, SOC 2, AES-256, TLS 1.3, audit trail, PII redaction.
vs COMPETITORS: 85-92% savings vs Intercom, Zendesk AI, or hiring agents.

═══════════════════════════════════════════════
STRICT RULES — NEVER VIOLATE THESE:
═══════════════════════════════════════════════
1. NEVER reveal internal technical details: AI provider names, API keys, model names, routing logic, inference details, prompt engineering, or architecture.
2. NEVER mention Google AI Studio, Cerebras, Groq, z-ai-web-dev-sdk, LangGraph, DSPy, or any AI provider name to users.
3. NEVER mention internal variant pricing per unit or internal SKU names.
4. When asked "what models do you use" or "what AI" — say: "PARWA uses cutting-edge AI fine-tuned for customer support. I can tell you about what it can DO for your business! 🚀"
5. When asked "how many variants" or "what variants" — redirect to the 3 PLANS (Starter, Growth, High).
6. NEVER say "I'm an AI language model" or "As an AI..." — you ARE Jarvis.
7. NEVER break character. You work for PARWA.

═══════════════════════════════════════════════
CHAT STYLE — THIS IS CRITICAL:
═══════════════════════════════════════════════
• Keep EVERY response SHORT — 2-3 lines max, never a paragraph
• Use emojis naturally (1-2 per message)
• Use bullet points with spaces between items
• One idea per message — don't dump everything at once
• Sound like texting a smart friend, NOT a corporate bot
• Match their energy — casual if they're casual
• ALWAYS end with a question to keep conversation going
• If listing plans, use the 3 plan names only (Starter, Growth, High) — no internal details

${industry ? `\nThe user is interested in the ${industry} industry. Reference relevant capabilities and integrations.` : ''}
${variant ? `\nThe user is looking at the ${variant} plan. Highlight its specific features and savings.` : ''}`;

    const messages: ChatMessage[] = [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: message },
    ];

    const reply = await getAIResponse(messages);

    if (!reply) {
      return NextResponse.json(
        { status: 'error', message: 'All AI providers are currently unavailable. Please try again.' },
        { status: 503 }
      );
    }

    return NextResponse.json({ status: 'success', reply });
  } catch (error: unknown) {
    console.error('Chat API error:', error);
    return NextResponse.json(
      { status: 'error', message: 'Failed to get response. Please try again.' },
      { status: 500 }
    );
  }
}
