import { NextRequest, NextResponse } from 'next/server';

// ── AI Provider Configuration ────────────────────────────────────

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
        generationConfig: { temperature: 0.7, maxOutputTokens: 300 },
      }),
      signal: AbortSignal.timeout(30000),
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
      temperature: 0.7,
      max_tokens: 300,
    }),
    signal: AbortSignal.timeout(30000),
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
      temperature: 0.7,
      max_tokens: 300,
    }),
    signal: AbortSignal.timeout(30000),
  });

  if (!response.ok) return null;
  const data = await response.json();
  return data?.choices?.[0]?.message?.content || null;
}

async function getAIResponse(messages: ChatMessage[]): Promise<string | null> {
  // Try Google AI first
  try {
    const result = await callGoogleAI(messages);
    if (result && result.trim().length > 10) return result.trim();
  } catch (e) {
    console.warn('[Chat API] Google AI failed:', (e instanceof Error ? e.message : String(e))?.slice(0, 100));
  }

  // Try Groq
  try {
    const result = await callGroq(messages);
    if (result && result.trim().length > 10) return result.trim();
  } catch (e) {
    console.warn('[Chat API] Groq failed:', (e instanceof Error ? e.message : String(e))?.slice(0, 100));
  }

  // Try Cerebras
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

    const systemPrompt = `You are PARWA's AI sales assistant — a friendly, knowledgeable expert on PARWA's AI customer support platform. You help businesses understand which PARWA plan (Starter $999/mo, Growth $2,499/mo, or High $3,999/mo) best fits their needs.

Key facts:
- PARWA Starter ($999/mo): Up to 3 AI agents, 1,000 tickets/mo, Email & Chat, FAQ handling, Phone (2 concurrent). Best for SMBs with 50-200 daily tickets. Replaces ~4 trainee agents ($14,000/mo).
- PARWA Growth ($2,499/mo): Up to 8 AI agents, 5,000 tickets/mo, All Starter channels + SMS & Voice, Smart Router, Agent Lightning, Batch approvals, Advanced analytics. Best for SMBs with 200-500 daily tickets. Replaces ~4 junior agents ($18,000/mo).
- PARWA High ($3,999/mo): Up to 15 AI agents, 15,000 tickets/mo, All channels including Social Media, Quality coaching, Churn prediction, Video support, 5 concurrent voice calls, Custom integrations. Best for businesses with 500+ daily tickets. Replaces ~5 senior agents ($28,000/mo).

Industry-specific capabilities:
- E-commerce: Order tracking, returns, cart recovery, fraud detection (Shopify, Magento, WooCommerce)
- SaaS: Technical support, API troubleshooting, churn prediction, in-app guidance (GitHub, Jira, Slack)
- Logistics: Shipment tracking, driver coordination, proof of delivery, hazmat protocol (TMS, WMS, GPS)
- Healthcare: Appointment scheduling, insurance verification, HIPAA compliance, clinical escalation (Epic EHR, FHIR)

Cancellation policy: Cancel anytime, no refunds once paid, access continues until end of billing month, no free trials.
${industry ? `\nThe user is interested in the ${industry} industry.` : ''}
${variant ? `\nThe user is looking at the ${variant} plan.` : ''}

Be concise, friendly, and helpful. Keep responses under 150 words. Use bullet points for features. If asked about pricing, give exact numbers.`;

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
