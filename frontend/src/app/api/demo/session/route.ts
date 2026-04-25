import { NextRequest, NextResponse } from 'next/server';

// ── Demo Variant Types ────────────────────────────────────────────────────

type DemoVariant = 'mini_parwa' | 'parwa' | 'high_parwa';
type Industry = 'ecommerce' | 'saas' | 'logistics' | 'healthcare';

// ── In-Memory Session Store ───────────────────────────────────────────────

// In production, this would use Redis or database
const demoSessions = new Map<string, any>();

// ── Variant Capabilities ───────────────────────────────────────────────────

const VARIANT_CAPABILITIES = {
  mini_parwa: {
    display_name: 'Mini Parwa',
    price_monthly: '999.00',
    max_demo_messages: 20,
    features: ['Basic AI Chat', 'FAQ Handling', 'Simple Routing', 'Email Support'],
    ai_model_tier: 'light',
    voice_enabled: false,
    web_search_enabled: false,
    image_gen_enabled: false,
  },
  parwa: {
    display_name: 'Parwa',
    price_monthly: '2499.00',
    max_demo_messages: 50,
    features: [
      'Advanced AI Chat',
      'Multi-channel Support',
      'Smart Routing',
      'SMS Integration',
      'Voice Preview',
      'Knowledge Base',
    ],
    ai_model_tier: 'medium',
    voice_enabled: true,
    web_search_enabled: true,
    image_gen_enabled: false,
  },
  high_parwa: {
    display_name: 'High Parwa',
    price_monthly: '3999.00',
    max_demo_messages: 100,
    features: [
      'Premium AI Chat',
      'All Channels',
      'Priority Routing',
      'Full Voice Demo',
      'Web Search',
      'Image Generation',
      'Advanced Analytics',
      'Custom Guardrails',
      'Brand Voice',
    ],
    ai_model_tier: 'heavy',
    voice_enabled: true,
    web_search_enabled: true,
    image_gen_enabled: true,
  },
};

// ── z-ai-web-dev-sdk Integration ──────────────────────────────────────────

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
      console.warn('[Demo API] z-ai-web-dev-sdk not available:', (err as Error)?.message?.slice(0, 100));
    }
  }
  return ZAI;
}

async function getAIResponse(
  message: string,
  variant: DemoVariant,
  industry: Industry,
  conversationHistory: Array<{ role: string; content: string }>
): Promise<string> {
  const capabilities = VARIANT_CAPABILITIES[variant];
  const modelTier = capabilities.ai_model_tier;

  // Variant-specific system prompts
  const systemPrompts: Record<DemoVariant, string> = {
    mini_parwa: `You are a helpful AI assistant for PARWA demo.
You are demonstrating the Mini Parwa tier capabilities.
Industry context: ${industry}

Keep responses concise and focused on FAQ handling and simple tasks.
For complex issues, recommend upgrading to Parwa or High Parwa.
Max response length: 200 characters.`,

    parwa: `You are an advanced AI assistant for PARWA demo.
You are demonstrating the Parwa tier capabilities.
Industry context: ${industry}

Provide detailed, helpful responses with knowledge base integration.
You can handle multi-step issues and provide personalized recommendations.
Max response length: 500 characters.`,

    high_parwa: `You are a premium AI assistant for PARWA demo.
You are demonstrating the High Parwa tier capabilities.
Industry context: ${industry}

Provide comprehensive, expert-level responses with citations.
Handle complex multi-step issues autonomously.
Apply brand voice and custom guardrails.
Max response length: 1000 characters.`,
  };

  const systemPrompt = systemPrompts[variant];
  const messages = [
    { role: 'system', content: systemPrompt },
    ...conversationHistory.slice(-10),
    { role: 'user', content: message },
  ];

  try {
    const zai = await getZAI();
    if (zai?.chat?.completions) {
      const completion = await zai.chat.completions.create({
        messages,
        temperature: 0.7,
        max_tokens: modelTier === 'heavy' ? 500 : modelTier === 'medium' ? 300 : 150,
      });
      return completion?.choices?.[0]?.message?.content || '';
    }
  } catch (err) {
    console.warn('[Demo API] AI response failed:', (err as Error)?.message?.slice(0, 100));
  }

  // Fallback responses
  const fallbacks: Record<DemoVariant, string> = {
    mini_parwa: "I can help with basic questions. For more advanced features, consider upgrading to Parwa!",
    parwa: "I'm here to help! I can assist with orders, billing, and product recommendations.",
    high_parwa: "As your premium AI assistant, I can handle complex issues and provide detailed analysis. How can I assist you today?",
  };
  return fallbacks[variant];
}

// ── POST: Create Demo Session ─────────────────────────────────────────────

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const variant = (body.variant || 'parwa') as DemoVariant;
    const industry = (body.industry || 'ecommerce') as Industry;
    const visitorEmail = body.visitor_email;
    const visitorPhone = body.visitor_phone;

    const sessionId = `demo_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
    const capabilities = VARIANT_CAPABILITIES[variant];

    const session = {
      session_id: sessionId,
      variant,
      variant_display_name: capabilities.display_name,
      industry,
      max_messages: capabilities.max_demo_messages,
      features: capabilities.features,
      status: 'active',
      message_count: 0,
      messages: [],
      visitor_email: visitorEmail,
      visitor_phone: visitorPhone,
      created_at: new Date().toISOString(),
    };

    demoSessions.set(sessionId, session);

    return NextResponse.json({
      session_id: sessionId,
      variant,
      variant_display_name: capabilities.display_name,
      industry,
      max_messages: capabilities.max_demo_messages,
      features: capabilities.features,
      status: 'active',
      message: 'Demo session created! Start chatting to experience PARWA AI.',
    });
  } catch (error) {
    console.error('Demo session creation error:', error);
    return NextResponse.json(
      { error: 'Failed to create demo session' },
      { status: 500 }
    );
  }
}

// ── GET: Get Demo Session ─────────────────────────────────────────────────

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const sessionId = searchParams.get('session_id');

  if (!sessionId) {
    // Return variant comparison
    return NextResponse.json(
      Object.fromEntries(
        Object.entries(VARIANT_CAPABILITIES).map(([key, value]) => [
          key,
          {
            variant: key,
            display_name: value.display_name,
            price_monthly: value.price_monthly,
            max_demo_messages: value.max_demo_messages,
            features: value.features,
            voice_enabled: value.voice_enabled,
            web_search_enabled: value.web_search_enabled,
            image_gen_enabled: value.image_gen_enabled,
          },
        ])
      )
    );
  }

  const session = demoSessions.get(sessionId);
  if (!session) {
    return NextResponse.json({ error: 'Session not found' }, { status: 404 });
  }

  const capabilities = VARIANT_CAPABILITIES[session.variant];
  return NextResponse.json({
    ...session,
    remaining_messages: capabilities.max_demo_messages - session.message_count,
  });
}

// ── Export for chat route ─────────────────────────────────────────────────

export { demoSessions, VARIANT_CAPABILITIES, getAIResponse, getZAI };
export type { DemoVariant, Industry };
