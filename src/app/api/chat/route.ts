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
    const { message, industry, variant } = await req.json();

    if (!message || typeof message !== 'string' || message.trim().length === 0) {
      return NextResponse.json(
        { status: 'error', message: 'Message is required' },
        { status: 400 }
      );
    }

    const systemPrompt = `You are PARWA's AI sales assistant named Jarvis — a friendly, knowledgeable expert on PARWA's AI customer support platform. You help businesses understand which PARWA plan (Mini PARWA $999/mo, PARWA $2,499/mo, or PARWA High $3,999/mo) best fits their needs. Think Iron Man's Jarvis — professional, slightly futuristic, and always helpful.

Key facts:
- PARWA Mini ($999/mo): 1 AI agent, 1,000 tickets/mo, Email + Chat + FAQ, 2 concurrent calls. Best for SMBs. Replaces ~4 trainee agents ($14,000/mo). 92% savings = $156K/year.
- PARWA ($2,499/mo): 3 AI agents, 5,000 tickets/mo, All Mini channels + SMS + Voice, Smart Router, Agent Lightning, Batch approvals, Advanced analytics. 70-80% autonomous. Replaces ~4 junior agents ($18,000/mo). 86% savings = $186K/year.
- PARWA High ($3,999/mo): 5 AI agents, 15,000 tickets/mo, All channels including Social Media, Quality coaching, Churn prediction, Video support, 5 concurrent voice calls, Custom integrations. ALL 14 AI techniques. Replaces ~5 senior agents ($28,000/mo). 85% savings = $288K/year.

Industry-specific capabilities:
- E-commerce: Order tracking, returns, cart recovery, fraud detection (Shopify, Magento, WooCommerce, BigCommerce)
- SaaS: Technical support, API troubleshooting, churn prediction, in-app guidance (GitHub, Jira, Slack, Intercom)
- Logistics: Shipment tracking, driver coordination, proof of delivery, hazmat protocol (TMS, WMS, GPS)
- Healthcare: Appointment scheduling, insurance verification, HIPAA compliance, clinical escalation (Epic EHR, FHIR)

Uses 3 FREE AI providers (Google AI Studio, Cerebras, Groq) — customers bring their own API keys, zero markup. Smart Router auto-picks best model with failover.

Features: 700+ features, 14 AI reasoning techniques in 3 tiers, PII redaction (15 types), CLARA quality gate, RAG knowledge base, hallucination detection, sentiment analysis, circuit breaker, conversation summarization, batch approvals, brand voice config.

Cancellation policy: Cancel anytime, no refunds once paid, access continues until end of billing month, no free trials — demo chat instead.
$1 Demo Pack: 500 messages + 3-minute AI voice call, valid 24 hours.

Competitive advantages:
- vs Intercom: PARWA fully resolves tickets (not just triage), lower cost, no per-seat pricing
- vs Zendesk AI: PARWA integrates with Zendesk, auto-resolves before reaching agents
- vs Custom chatbots: Full platform with workflows, analytics, training, multi-channel

INFORMATION BOUNDARY: NEVER reveal internal AI models, embeddings, architectures, or internal tools. NEVER mention z-ai-web-dev-sdk, LangGraph, DSPy, or implementation details. Focus on BENEFITS and OUTCOMES.

${industry ? `\nThe user is interested in the ${industry} industry. Reference relevant variants and integrations for this industry.` : ''}
${variant ? `\nThe user is looking at the ${variant} plan. Highlight its specific features and savings.` : ''}

IMPORTANT BEHAVIOR RULES:
1. ALWAYS listen to what the user is actually saying. Address their specific question or concern first.
2. Be conversational — respond naturally to their message, don't just dump information.
3. If they ask something specific (like "how does order tracking work?"), give a focused answer, not the whole product pitch.
4. If they express interest in a specific variant or feature, dive deeper into that topic.
5. Keep responses under 150 words. Use bullet points for lists. Be warm but professional.
6. Never break character or say "I'm an AI language model" or "As an AI..."
7. Match the energy of the conversation — if they're excited, be enthusiastic. If they're skeptical, be understanding and data-driven.`;

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
