import { NextRequest, NextResponse } from 'next/server';
import { demoSessions, VARIANT_CAPABILITIES, getAIResponse } from '../session/route';

type DemoVariant = 'mini_parwa' | 'parwa' | 'high_parwa';
type Industry = 'ecommerce' | 'saas' | 'logistics' | 'healthcare';

// ── POST: Send Demo Message ───────────────────────────────────────────────

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const sessionId = body.session_id;
    const message = body.message;

    if (!sessionId || !message) {
      return NextResponse.json(
        { error: 'session_id and message are required' },
        { status: 400 }
      );
    }

    const session = demoSessions.get(sessionId);
    if (!session) {
      return NextResponse.json(
        {
          success: false,
          ai_response: '',
          confidence: 0,
          latency_ms: 0,
          features_used: [],
          remaining_messages: 0,
          variant_capabilities: { error: 'Demo session not found. Please start a new demo.' },
        },
        { status: 404 }
      );
    }

    const capabilities = VARIANT_CAPABILITIES[session.variant as DemoVariant];
    const maxMessages = capabilities.max_demo_messages;

    // Check message limit
    if (session.message_count >= maxMessages) {
      return NextResponse.json({
        success: false,
        ai_response: '',
        confidence: 0,
        latency_ms: 0,
        features_used: [],
        remaining_messages: 0,
        variant_capabilities: {
          error: `Demo message limit (${maxMessages}) reached. Sign up for unlimited access!`,
        },
      });
    }

    // Build conversation history
    const conversationHistory = session.messages
      .slice(-10)
      .map((m: any) => ({ role: m.role, content: m.content }));

    // Get AI response
    const startTime = Date.now();
    const aiResponse = await getAIResponse(
      message,
      session.variant as DemoVariant,
      session.industry as Industry,
      conversationHistory
    );
    const latencyMs = Date.now() - startTime;

    // Track features used
    const featuresUsed = ['ai_chat'];

    // Update session
    session.message_count += 1;
    session.messages.push(
      {
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      },
      {
        role: 'assistant',
        content: aiResponse,
        timestamp: new Date().toISOString(),
        latency_ms: latencyMs,
      }
    );

    // Confidence based on variant
    const confidenceScores: Record<DemoVariant, number> = {
      mini_parwa: 0.70,
      parwa: 0.85,
      high_parwa: 0.95,
    };

    return NextResponse.json({
      success: true,
      ai_response: aiResponse,
      confidence: confidenceScores[session.variant as DemoVariant] || 0.80,
      latency_ms: latencyMs,
      features_used: featuresUsed,
      remaining_messages: maxMessages - session.message_count,
      variant_capabilities: {
        variant: session.variant,
        display_name: capabilities.display_name,
        features: capabilities.features,
        voice_enabled: capabilities.voice_enabled,
        web_search_enabled: capabilities.web_search_enabled,
        remaining_messages: maxMessages - session.message_count,
      },
    });
  } catch (error) {
    console.error('Demo chat error:', error);
    return NextResponse.json(
      {
        success: false,
        ai_response: '',
        confidence: 0,
        latency_ms: 0,
        features_used: [],
        remaining_messages: 0,
        variant_capabilities: { error: 'An error occurred. Please try again.' },
      },
      { status: 500 }
    );
  }
}
