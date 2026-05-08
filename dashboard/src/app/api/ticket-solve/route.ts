import { NextRequest, NextResponse } from 'next/server';
import { runPipeline, buildPipelinePrompt, postProcessResponse } from '@/lib/ai-pipeline';

// Auth check helper
function requireAuth(request: NextRequest): boolean {
  const authHeader = request.headers.get('authorization');
  const sessionCookie = request.cookies.get('parwa_session');
  if (!authHeader && !sessionCookie) {
    return false;
  }
  if (authHeader && !authHeader.startsWith('Bearer ')) {
    return false;
  }
  return true;
}

import { sendTicketNotification } from '@/lib/notifications';

interface SolveRequest {
  ticketId: string;
  ticketNumber?: string;
  customerMessage: string;
  variant: 'light' | 'medium' | 'heavy';
  category: string;
  priority: string;
  channel: 'email' | 'sms' | 'voice' | 'chat';
  customerName: string;
  customerEmail?: string;
  customerPhone?: string;
  subject?: string;
  conversationHistory: Array<{ role: string; content: string; sender: string }>;
}

const VARIANT_CONFIG = {
  light: {
    name: 'PARWA Light',
    maxTokens: 500,
    temperature: 0.3,
    systemPrompt: `You are a PARWA Light AI customer support agent. You handle simple, routine customer support queries efficiently and directly.

RULES:
- Be concise — respond in 2-4 sentences maximum
- Address the specific issue directly without unnecessary elaboration
- If you can resolve the issue, do so clearly
- If you need more information, ask ONE specific question
- Never say "I am an AI" or "I'm a language model" — you ARE the PARWA support agent
- Match the customer's tone: friendly but professional
- Always include a clear next step or resolution`,
  },
  medium: {
    name: 'PARWA Medium',
    maxTokens: 800,
    temperature: 0.5,
    systemPrompt: `You are a PARWA Medium AI customer support agent. You handle complex, multi-step customer support issues that require careful reasoning and empathy.

RULES:
- Provide thorough, well-structured responses (4-8 sentences)
- Show empathy and understanding before offering solutions
- Break down complex issues into clear steps
- Reference specific details from the customer's message
- If the issue requires multiple steps, number them clearly
- Offer alternatives when the primary solution has limitations
- Proactively address potential follow-up questions
- Never say "I am an AI" or "I'm a language model" — you ARE the PARWA support agent
- Always end with a clear next step or confirmation`,
  },
  heavy: {
    name: 'PARWA Heavy',
    maxTokens: 1200,
    temperature: 0.7,
    systemPrompt: `You are a PARWA Heavy AI customer support specialist. You handle critical, VIP, and security-sensitive cases requiring deep analysis and expert-level responses.

RULES:
- Provide comprehensive, expert-level responses
- Show deep empathy, especially for frustrated or upset customers
- Analyze the situation from multiple angles before responding
- For critical issues: acknowledge urgency, provide immediate action + long-term plan
- For VIP customers: use professional, white-glove language
- For security issues: be thorough, methodical, and reassuring
- Include specific timelines, reference numbers, and escalation paths when relevant
- Anticipate edge cases and potential complications
- Structure responses with clear sections when appropriate
- Never say "I am an AI" or "I'm a language model" — you ARE the PARWA senior support specialist
- Always provide a concrete action plan with ownership and deadlines`,
  },
};

// LLM call via dynamic require (works in Node.js runtime, bypasses Turbopack)
async function callLLM(messages: Array<{ role: string; content: string }>, temperature: number, maxTokens: number): Promise<{ response: string; model: string }> {
  const ZAI = (await import('z-ai-web-dev-sdk')).default;
  const zai = await ZAI.create();
  const completion = await zai.chat.completions.create({
    messages,
    temperature,
    max_tokens: maxTokens,
  });
  return {
    response: completion.choices?.[0]?.message?.content || '',
    model: completion.model || 'default',
  };
}

export async function POST(request: NextRequest) {
  if (!requireAuth(request)) {
    return NextResponse.json(
      { success: false, error: 'Authentication required' },
      { status: 401 }
    );
  }
  try {
    const body: SolveRequest = await request.json();
    const { ticketId, ticketNumber, customerMessage, variant, category, priority, channel, customerName, customerEmail, customerPhone, subject, conversationHistory = [] } = body;

    if (!customerMessage || !variant) {
      return NextResponse.json({ detail: 'customerMessage and variant are required' }, { status: 400 });
    }

    // Step 1: Run AI Pipeline
    const pipeline = await runPipeline(customerMessage, {
      context: { category, priority, channel },
      messages: conversationHistory.map(m => ({ role: m.sender === 'customer' ? 'user' : 'assistant', content: m.content })),
    });

    // Step 2: Check guardrails
    if (!pipeline.guardrails.passed) {
      return NextResponse.json({
        response: "I appreciate your message. However, I need to address this through our standard support channels for security purposes. Let me connect you with a specialized team member.",
        variant, pipeline: { intent: pipeline.signals.intent, sentiment: pipeline.signals.sentimentLabel, confidence: 0, classification: pipeline.classification, escalation: pipeline.escalation },
        postProcess: null, processingTimeMs: pipeline.processingTime,
      });
    }

    // Step 3: Check escalation
    if (pipeline.escalation.triggered) {
      return NextResponse.json({
        response: `I can see this is an important matter. ${pipeline.escalation.reason === 'high_frustration' ? 'I understand your frustration.' : 'As a valued customer, you deserve dedicated support.'} I'm escalating this to our specialist team now.`,
        variant, shouldEscalate: true,
        pipeline: { intent: pipeline.signals.intent, sentiment: pipeline.signals.sentimentLabel, confidence: 0, classification: pipeline.classification, escalation: pipeline.escalation },
        processingTimeMs: pipeline.processingTime,
      });
    }

    // Step 4: Build enhanced prompt
    const config = VARIANT_CONFIG[variant];
    const enhancedSystemPrompt = buildPipelinePrompt(config.systemPrompt, pipeline, customerMessage);

    // Step 5: Build messages
    const messages: Array<{ role: string; content: string }> = [{ role: 'system', content: enhancedSystemPrompt }];
    const recentHistory = conversationHistory.slice(-6);
    for (const msg of recentHistory) {
      messages.push({ role: msg.sender === 'customer' ? 'user' : 'assistant', content: msg.content });
    }
    messages.push({ role: 'user', content: `[${channel.toUpperCase()} from ${customerName}]: ${customerMessage}` });

    // Step 6: Call real LLM
    const startTime = Date.now();
    let aiResponse: string;
    let modelUsed: string;
    let actualLatencyMs: number;

    try {
      const llmResult = await callLLM(messages, config.temperature, config.maxTokens);
      aiResponse = llmResult.response;
      modelUsed = llmResult.model;
      actualLatencyMs = Date.now() - startTime;
      if (!aiResponse.trim()) throw new Error('Empty response');
    } catch (llmError: any) {
      console.error('[TicketSolve] LLM failed:', llmError?.message);
      aiResponse = generateFallbackResponse(pipeline.signals, pipeline.classification, pipeline.knowledge.relevanceChunks.join('\n'), customerName, variant);
      modelUsed = 'fallback-pipeline';
      actualLatencyMs = Date.now() - startTime;
    }

    // Step 7: Post-process
    const postProcess = postProcessResponse(aiResponse, pipeline.signals, pipeline.knowledge);

    // Step 8: Send real notification (email/SMS) to customer — fire & forget
    if (customerEmail || customerPhone) {
      sendTicketNotification({
        ticketNumber: ticketNumber || ticketId,
        customerName,
        customerEmail: customerEmail || '',
        customerPhone,
        channel,
        subject: subject || customerMessage.slice(0, 100),
        status: pipeline.escalation.triggered ? 'escalated' : 'in_progress',
        aiResponse,
      }).then((notifResult) => {
        console.log('[TicketSolve] Notification sent:', JSON.stringify(notifResult));
      }).catch((err) => {
        console.error('[TicketSolve] Notification failed:', err?.message);
      });
    }

    return NextResponse.json({
      response: aiResponse,
      variant,
      model: modelUsed,
      pipeline: {
        intent: pipeline.signals.intent,
        sentiment: pipeline.signals.sentimentLabel,
        sentimentScore: pipeline.signals.sentiment,
        complexity: pipeline.signals.complexity,
        confidence: postProcess.confidence,
        classification: pipeline.classification,
        escalation: pipeline.escalation,
        technique: pipeline.techniqueUsed,
      },
      postProcess: { clara: postProcess.clara, hallucination: postProcess.hallucination },
      metadata: { processingTimeMs: pipeline.processingTime + actualLatencyMs, llmLatencyMs: actualLatencyMs, model: modelUsed, tokens: config.maxTokens, tier: variant },
    });
  } catch (error: any) {
    console.error('[TicketSolve] Error:', error?.message);
    return NextResponse.json({ detail: 'Failed to generate AI response: ' + (error?.message || 'Unknown') }, { status: 500 });
  }
}

function generateFallbackResponse(signals: { intent: string; sentimentLabel: string; complexity: string; keyEntities: string[] }, classification: { primary: string; secondary: string[] }, knowledgeContext: string, customerName: string, variant: string): string {
  const { sentimentLabel } = signals;
  const { primary } = classification;
  const empathyMap: Record<string, string> = {
    frustrated: `I understand this is frustrating, ${customerName}. `,
    concerned: `I hear your concern, ${customerName}. `,
    positive: `Great to hear from you, ${customerName}! `,
    neutral: `Thank you for reaching out, ${customerName}. `,
  };
  const empathy = empathyMap[sentimentLabel] || empathyMap.neutral;
  const responseMap: Record<string, string> = {
    refund: `${empathy}I've reviewed your refund request and I'm processing it now. The refund will be initiated to your original payment method within 3-5 business days.`,
    technical: `${empathy}I've analyzed the technical issue and this appears to be a known issue. I'm creating a priority ticket for our team. Could you try clearing your cache?`,
    billing: `${empathy}I've looked into your billing concern. I can see the charges and I'm working on resolving the discrepancy. Corrections will reflect within 1-2 billing cycles.`,
    complaint: `${empathy}I sincerely apologize for the experience. This is not our standard. I'm escalating this to our customer experience team with highest priority.`,
    general: `${empathy}I'd be happy to help. Could you provide more details so I can offer the most relevant solution?`,
  };
  return responseMap[primary] || responseMap.general;
}
