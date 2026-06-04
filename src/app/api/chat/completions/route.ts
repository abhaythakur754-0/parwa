import { NextRequest, NextResponse } from 'next/server';

/**
 * POST /api/chat/completions — OpenAI-Compatible LLM Proxy via ZAI SDK
 *
 * This route provides an OpenAI-compatible /chat/completions endpoint
 * that uses the z-ai-web-dev-sdk (ZAI SDK) for LLM access.
 *
 * The Python backend's llm_gateway.py (ZAI_GATEWAY mode) calls this
 * endpoint when LLM_PROVIDER=zai_gateway is set in .env.
 *
 * This eliminates the need for individual Google AI / Cerebras / Groq
 * API keys — the ZAI SDK handles everything.
 */

let ZAI: any = null;

async function getZAI() {
  if (!ZAI) {
    try {
      const mod = await import('z-ai-web-dev-sdk');
      const ZAIClass = (mod as any).default;
      if (ZAIClass && typeof ZAIClass.create === 'function') {
        ZAI = await ZAIClass.create();
        console.log('[LLM Proxy] ZAI SDK initialized successfully');
      }
    } catch (err) {
      console.warn('[LLM Proxy] z-ai-web-dev-sdk not available:', (err instanceof Error ? err.message : String(err))?.slice(0, 150));
    }
  }
  return ZAI;
}

// Fallback providers (used only if ZAI SDK is unavailable)
const GOOGLE_AI_KEY = process.env.GOOGLE_AI_API_KEY;
const GROQ_KEY = process.env.GROQ_API_KEY;
const CEREBRAS_KEY = process.env.CEREBRAS_API_KEY;

interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

async function callZAI(
  messages: ChatMessage[],
  max_tokens: number,
  temperature: number,
): Promise<{ text: string; model: string; tokens: number } | null> {
  try {
    const zai = await getZAI();
    if (!zai || !zai.chat || !zai.chat.completions) return null;

    const completion = await zai.chat.completions.create({
      messages: messages.map(m => ({
        role: m.role as 'system' | 'user' | 'assistant',
        content: m.content,
      })),
      temperature,
      max_tokens,
    });

    const text = completion?.choices?.[0]?.message?.content;
    const tokens = completion?.usage?.total_tokens || 0;
    const model = completion?.model || 'zai-default';

    if (text && text.trim().length > 0) {
      return { text: text.trim(), model, tokens };
    }
    return null;
  } catch (err) {
    console.warn('[LLM Proxy] ZAI SDK failed:', (err instanceof Error ? err.message : String(err))?.slice(0, 200));
    return null;
  }
}

async function callGoogleAI(
  messages: ChatMessage[],
  max_tokens: number,
  temperature: number,
): Promise<{ text: string; model: string; tokens: number } | null> {
  if (!GOOGLE_AI_KEY) return null;
  try {
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
          generationConfig: { temperature, maxOutputTokens: max_tokens },
        }),
        signal: AbortSignal.timeout(30000),
      }
    );

    if (!response.ok) return null;
    const data = await response.json();
    const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (text && text.trim().length > 0) {
      return { text: text.trim(), model: 'gemini-2.0-flash', tokens: data?.usageMetadata?.totalTokenCount || 0 };
    }
    return null;
  } catch (err) {
    console.warn('[LLM Proxy] Google AI failed:', (err instanceof Error ? err.message : String(err))?.slice(0, 100));
    return null;
  }
}

async function callGroq(
  messages: ChatMessage[],
  max_tokens: number,
  temperature: number,
): Promise<{ text: string; model: string; tokens: number } | null> {
  if (!GROQ_KEY) return null;
  try {
    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${GROQ_KEY}`,
      },
      body: JSON.stringify({
        model: 'llama-3.3-70b-versatile',
        messages,
        temperature,
        max_tokens,
      }),
      signal: AbortSignal.timeout(30000),
    });

    if (!response.ok) return null;
    const data = await response.json();
    const text = data?.choices?.[0]?.message?.content;
    if (text && text.trim().length > 0) {
      return { text: text.trim(), model: data?.model || 'llama-3.3-70b-versatile', tokens: data?.usage?.total_tokens || 0 };
    }
    return null;
  } catch (err) {
    console.warn('[LLM Proxy] Groq failed:', (err instanceof Error ? err.message : String(err))?.slice(0, 100));
    return null;
  }
}

async function callCerebras(
  messages: ChatMessage[],
  max_tokens: number,
  temperature: number,
): Promise<{ text: string; model: string; tokens: number } | null> {
  if (!CEREBRAS_KEY) return null;
  try {
    const response = await fetch('https://api.cerebras.ai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${CEREBRAS_KEY}`,
      },
      body: JSON.stringify({
        model: 'llama-4-scout-17b-16e-instruct',
        messages,
        temperature,
        max_tokens,
      }),
      signal: AbortSignal.timeout(30000),
    });

    if (!response.ok) return null;
    const data = await response.json();
    const text = data?.choices?.[0]?.message?.content;
    if (text && text.trim().length > 0) {
      return { text: text.trim(), model: data?.model || 'llama-4-scout', tokens: data?.usage?.total_tokens || 0 };
    }
    return null;
  } catch (err) {
    console.warn('[LLM Proxy] Cerebras failed:', (err instanceof Error ? err.message : String(err))?.slice(0, 100));
    return null;
  }
}

// ── Smart Router: ZAI SDK first, then fallbacks ──

async function getLLMResponse(
  messages: ChatMessage[],
  max_tokens: number,
  temperature: number,
): Promise<{ text: string; model: string; tokens: number } | null> {
  // Priority 1: ZAI SDK (no API key needed — built into the platform)
  const zaiResult = await callZAI(messages, max_tokens, temperature);
  if (zaiResult) return zaiResult;

  // Priority 2: Google AI (if key configured)
  const googleResult = await callGoogleAI(messages, max_tokens, temperature);
  if (googleResult) return googleResult;

  // Priority 3: Groq (if key configured)
  const groqResult = await callGroq(messages, max_tokens, temperature);
  if (groqResult) return groqResult;

  // Priority 4: Cerebras (if key configured)
  const cerebrasResult = await callCerebras(messages, max_tokens, temperature);
  if (cerebrasResult) return cerebrasResult;

  return null;
}

export async function POST(req: NextRequest) {
  try {
    // Optional: Verify API key if ZAI_API_KEY is set
    const apiKey = process.env.ZAI_API_KEY;
    if (apiKey) {
      const authHeader = req.headers.get('authorization');
      if (!authHeader || !authHeader.startsWith('Bearer ') || authHeader.slice(7) !== apiKey) {
        return NextResponse.json(
          { error: { message: 'Invalid API key', type: 'auth_error' } },
          { status: 401 }
        );
      }
    }

    const body = await req.json();
    const {
      model: requestedModel,
      messages,
      max_tokens = 300,
      temperature = 0.5,
    } = body;

    if (!messages || !Array.isArray(messages) || messages.length === 0) {
      return NextResponse.json(
        { error: { message: 'messages is required and must be a non-empty array', type: 'invalid_request' } },
        { status: 400 }
      );
    }

    // Call LLM via ZAI SDK → fallback chain
    const result = await getLLMResponse(
      messages as ChatMessage[],
      max_tokens,
      temperature,
    );

    if (!result) {
      return NextResponse.json(
        { error: { message: 'All LLM providers are currently unavailable', type: 'server_error' } },
        { status: 503 }
      );
    }

    // Return OpenAI-compatible response format
    const responseId = `chatcmpl-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    return NextResponse.json({
      id: responseId,
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: result.model,
      choices: [
        {
          index: 0,
          message: {
            role: 'assistant',
            content: result.text,
          },
          finish_reason: 'stop',
        },
      ],
      usage: {
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: result.tokens,
      },
    });
  } catch (error: unknown) {
    console.error('[LLM Proxy] Error:', error);
    return NextResponse.json(
      { error: { message: 'Internal server error', type: 'server_error' } },
      { status: 500 }
    );
  }
}

// Handle GET requests (for health check / discovery)
export async function GET() {
  return NextResponse.json({
    service: 'parwa-llm-proxy',
    version: '1.0.0',
    providers: [
      { name: 'zai_sdk', priority: 1, status: 'available' },
      { name: 'google_ai', priority: 2, status: GOOGLE_AI_KEY ? 'configured' : 'not_configured' },
      { name: 'groq', priority: 3, status: GROQ_KEY ? 'configured' : 'not_configured' },
      { name: 'cerebras', priority: 4, status: CEREBRAS_KEY ? 'configured' : 'not_configured' },
    ],
  });
}
