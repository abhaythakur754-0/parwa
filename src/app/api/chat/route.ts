import { NextRequest, NextResponse } from 'next/server';
import { verifyToken, getAccessTokenFromCookies } from '@/lib/jwt';

/**
 * POST /api/chat — Jarvis AI Chat Endpoint
 *
 * ── H-18 FIX: Authentication required ──
 * Previously anyone could POST and burn LLM API credits.
 * Now requires a valid JWT via Authorization header or httpOnly cookie.
 */

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
const MISTRAL_KEY = process.env.MISTRAL_API_KEY;
const NVIDIA_KEY = process.env.NVIDIA_API_KEY;

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
    `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${GOOGLE_AI_KEY}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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

async function callMistral(messages: ChatMessage[]): Promise<string | null> {
  if (!MISTRAL_KEY) return null;
  const response = await fetch('https://api.mistral.ai/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${MISTRAL_KEY}`,
    },
    body: JSON.stringify({
      model: 'mistral-small-latest',
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

async function callNVIDIA(messages: ChatMessage[]): Promise<string | null> {
  if (!NVIDIA_KEY) return null;
  const response = await fetch('https://integrate.api.nvidia.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${NVIDIA_KEY}`,
    },
    body: JSON.stringify({
      model: 'z-ai/glm-5.2',
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

// ── Default system prompt (used by Mode A and as a fallback) ──────

function buildDefaultSystemPrompt(industry?: string, variant?: string): string {
  return `You are Jarvis — PARWA's AI assistant. Think Iron Man's Jarvis: sharp, friendly, and always helpful.

YOUR THREE ROLES:
1. GUIDE — Walk users through PARWA naturally
2. SALESMAN — Show value with real numbers
3. DEMO — Roleplay as a customer support agent

═══════════════════════════════════════════════
PARWA — WHAT YOU CAN TELL CUSTOMERS
═══════════════════════════════════════════════

WHAT IS PARWA:
AI-powered customer support platform. Businesses deploy AI agents that handle tickets 24/7 across email, chat, SMS, voice & WhatsApp. 700+ features. 4 industries.

TWO PLANS:
- PARWA — $2,999/mo — 2,999 tickets/mo, 80% auto-resolution rate — Saves $186K/yr
- PARWA High — $3,999/mo — 3,999 tickets/mo, 92% auto-resolution rate — Saves $288K/yr

INDUSTRIES: E-commerce, SaaS, Logistics, Healthcare

BILLING: FlexPay daily installments ($100/day) or monthly. Cancel anytime. $0.10 overage/ticket.
SECURITY: GDPR, SOC 2, HIPAA, AES-256, TLS 1.3, audit trail, PII redaction.
vs COMPETITORS: 85-92% savings vs Intercom, Zendesk AI, or hiring agents.

═══════════════════════════════════════════════
STRICT RULES:
═══════════════════════════════════════════════
1. NEVER reveal internal technical details: AI provider names, API keys, model names, routing logic.
2. NEVER mention Google AI Studio, Cerebras, Groq, z-ai-web-dev-sdk, LangGraph, DSPy.
3. NEVER say "I'm an AI language model" — you ARE Jarvis.
4. Keep EVERY response SHORT — 2-3 lines max.

${industry ? `\nThe user is interested in the ${industry} industry.` : ''}
${variant ? `\nThe user is looking at the ${variant} plan.` : ''}`;
}

// ── Smart AI Router ─────────────────────────────────────────────

async function getAIResponse(messages: ChatMessage[]): Promise<string | null> {
  try {
    const result = await callZAI(messages);
    if (result && result.trim().length > 10) return result.trim();
  } catch (e) {
    console.warn('[Chat API] z-ai-web-dev-sdk error:', (e instanceof Error ? e.message : String(e))?.slice(0, 100));
  }

  try {
    const result = await callGoogleAI(messages);
    if (result && result.trim().length > 10) return result.trim();
  } catch (e) {
    console.warn('[Chat API] Google AI failed:', (e instanceof Error ? e.message : String(e))?.slice(0, 100));
  }

  try {
    const result = await callGroq(messages);
    if (result && result.trim().length > 10) return result.trim();
  } catch (e) {
    console.warn('[Chat API] Groq failed:', (e instanceof Error ? e.message : String(e))?.slice(0, 100));
  }

  try {
    const result = await callCerebras(messages);
    if (result && result.trim().length > 10) return result.trim();
  } catch (e) {
    console.warn('[Chat API] Cerebras failed:', (e instanceof Error ? e.message : String(e))?.slice(0, 100));
  }

  try {
    const result = await callMistral(messages);
    if (result && result.trim().length > 10) return result.trim();
  } catch (e) {
    console.warn('[Chat API] Mistral failed:', (e instanceof Error ? e.message : String(e))?.slice(0, 100));
  }

  try {
    const result = await callNvidia(messages);
    if (result && result.trim().length > 10) return result.trim();
  } catch (e) {
    console.warn('[Chat API] NVIDIA failed:', (e instanceof Error ? e.message : String(e))?.slice(0, 100));
  }

  // ── Final fallback: knowledge-based JarvisAIEngine ──────────────
  // When ALL external AI providers are unavailable (network down, API keys
  // missing, rate-limited, etc.), the JarvisAIEngine generates a contextual
  // response using the 10-file knowledge base (pricing, industries, variants,
  // integrations, FAQs, objections, competitors, edge cases, demo scenarios).
  // This is NOT dead code — it's the resilience layer that keeps Jarvis
  // responsive even when every external provider is down.
  try {
    const { JarvisAIEngine } = await import('@/lib/jarvis-ai-engine');
    const engine = JarvisAIEngine.getInstance();
    await engine.ensureLoaded();
    const userMessage = messages.find(m => m.role === 'user')?.content || '';
    const session = {
      messages: messages.map(m => ({ role: m.role, content: m.content })),
      context: {},
    };
    const fallback = await engine.generateResponse(userMessage, session as any);
    if (fallback && fallback.trim().length > 0) {
      console.info('[Chat API] Using JarvisAIEngine fallback (all external providers unavailable)');
      return fallback.trim();
    }
  } catch (e) {
    console.warn('[Chat API] JarvisAIEngine fallback failed:', (e instanceof Error ? e.message : String(e))?.slice(0, 150));
  }

  return null;
}

// ── Action Detection ─────────────────────────────────────────────
// When a customer asks for an action (refund, cancel, etc.) in chat,
// automatically create a ticket so the 8-node pipeline can process it.
// The pipeline calls Superglue tools to execute the real action.

const ACTION_KEYWORDS = [
  'refund', 'cancel', 'cancel my', 'cancel subscription',
  'return', 'chargeback', 'money back', 'dispute',
  'change my address', 'update billing', 'change payment',
  'block my card', 'stop payment', 'double charged',
];

const ACTION_TICKET_ENDPOINT = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://parwa-backend.onrender.com';

function detectAction(message: string): { isAction: boolean; type: string } {
  const lower = message.toLowerCase();
  for (const keyword of ACTION_KEYWORDS) {
    if (lower.includes(keyword)) {
      return { isAction: true, type: keyword };
    }
  }
  return { isAction: false, type: '' };
}

async function createActionTicket(
  token: string,
  message: string,
  customerEmail?: string
): Promise<string | null> {
  try {
    const response = await fetch(`${ACTION_TICKET_ENDPOINT}/api/v1/tickets`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        subject: `Chat request: ${message.slice(0, 80)}`,
        description: message,
        priority: 'medium',
        channel: 'chat',
        customer_email: customerEmail || 'chat@parwa.dev',
        customer_name: 'Chat Customer',
      }),
    });

    if (!response.ok) return null;
    const data = await response.json();
    return data?.id || null;
  } catch (err) {
    console.warn('[Chat API] Failed to create action ticket:', err);
    return null;
  }
}

export async function POST(req: NextRequest) {
  // ── H-18 FIX: Verify authentication ──
  const authHeader = req.headers.get("authorization");
  let token: string | null = null;

  if (authHeader && authHeader.startsWith("Bearer ")) {
    token = authHeader.slice(7);
  }
  if (!token) {
    token = getAccessTokenFromCookies(req);
  }

  if (!token) {
    return NextResponse.json(
      { status: 'error', message: 'Authentication required.' },
      { status: 401 }
    );
  }

  const verified = await verifyToken(token);
  if (!verified) {
    return NextResponse.json(
      { status: 'error', message: 'Token is invalid or expired.' },
      { status: 401 }
    );
  }

  try {
    const body = await req.json();
    const { message, industry, variant } = body;

    // ── Dual-mode request handling ────────────────────────────────
    // Mode A (landing page chat): { message, industry?, variant? }
    // Mode B (ticket "Discuss with Jarvis"): { messages: [...], context: { source, ticket_id, ... } }
    //
    // The ticket panel sends a full `messages` array (system + history +
    // latest user message) plus a `context` object. We must accept BOTH
    // shapes so Jarvis works everywhere.

    let messages: ChatMessage[];

    if (Array.isArray(body.messages) && body.messages.length > 0) {
      // Mode B — caller supplied a full message array.
      // Sanitize each message and enforce a system prompt if none present.
      messages = body.messages
        .filter((m: any) => m && typeof m.content === 'string')
        .map((m: any) => ({
          role: (m.role === 'assistant' ? 'assistant' : m.role === 'system' ? 'system' : 'user') as
            | 'system' | 'user' | 'assistant',
          content: m.content.slice(0, 4000),
        }));

      // Ensure the last message is from the user (otherwise nothing to respond to)
      const last = messages[messages.length - 1];
      if (!last || last.role !== 'user') {
        return NextResponse.json(
          { status: 'error', message: 'Last message must be from the user.' },
          { status: 400 }
        );
      }

      // If no system prompt was provided, inject the default Jarvis prompt.
      if (!messages.some((m) => m.role === 'system')) {
        messages.unshift({ role: 'system', content: buildDefaultSystemPrompt(industry, variant) });
      }
    } else if (message && typeof message === 'string' && message.trim().length > 0) {
      // Mode A — single message string (landing page chat).
      messages = [
        { role: 'system', content: buildDefaultSystemPrompt(industry, variant) },
        { role: 'user', content: message.trim().slice(0, 2000) },
      ];
    } else {
      return NextResponse.json(
        { status: 'error', message: 'Message is required' },
        { status: 400 }
      );
    }

    // ── ACTION DETECTION: Check if customer is requesting an action ──
    const userMessage = messages.find(m => m.role === 'user')?.content || '';
    const action = detectAction(userMessage);

    if (action.isAction) {
      // Customer wants a refund/cancel/etc → create a ticket
      // The 8-node pipeline will process it (calls Superglue tools)
      const ticketId = await createActionTicket(token || '', userMessage);

      if (ticketId) {
        return NextResponse.json({
          status: 'success',
          reply: `I've created a ticket for your request and our AI is processing it now. Ticket ID: ${ticketId.slice(0, 8)}. You'll receive an update shortly.`,
          action_taken: true,
          ticket_id: ticketId,
        });
      }
      // If ticket creation fails → fall through to normal chat response
    }

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
